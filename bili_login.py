#!/usr/bin/env python3
"""B站扫码登录：跟随 crossDomain URL 获取 cookie"""

import asyncio
import json
from pathlib import Path

import aiohttp
from bilibili_api.login_v2 import QrCodeLogin
from bilibili_api.utils.network import Api, Credential
from bilibili_api.utils.utils import get_api

API = get_api("login")
CRED_FILE = Path(__file__).parent / "bili_credential.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://passport.bilibili.com/",
    "Origin": "https://passport.bilibili.com",
    "Accept": "application/json, text/plain, */*",
}


def parse_cookies(set_cookie_headers):
    cookies = {}
    for c in set_cookie_headers:
        name, _, val = c.partition("=")
        cookies[name.strip()] = val.split(";")[0]
    return cookies


async def main():
    qr = QrCodeLogin()
    await qr.generate_qrcode()
    key = qr._QrCodeLogin__qr_key
    pic = qr.get_qrcode_picture()
    Path(__file__).parent.joinpath("qrcode_login.png").write_bytes(pic.content)
    print("请用B站App扫码（或打开 qrcode_login.png）", flush=True)
    print(qr.get_qrcode_terminal(), flush=True)
    print("\n等待扫码...", flush=True)

    while True:
        events = (
            await Api(credential=Credential(), **API["qrcode"]["web"]["get_events"])
            .update_params(qrcode_key=key)
            .result
        )
        code = events.get("code")
        if code == 0:
            break
        if code == 86038:
            print("二维码已过期，请重新运行", flush=True)
            return
        if code == 86090:
            print("已扫码，请在手机上确认...", flush=True)
        elif code == 86101:
            print("等待扫码...", flush=True)
        await asyncio.sleep(2)

    url = events.get("url", "")
    print("SUCCESS_URL:", url, flush=True)

    # 方式A: 不跟随重定向，直接取 Set-Cookie
    print("\n--- 方式A: GET crossDomain (不跟随重定向) ---", flush=True)
    jar = {}
    async with aiohttp.ClientSession(headers=HEADERS) as s:
        async with s.get(url, allow_redirects=False) as r:
            print("status:", r.status, flush=True)
            for k, v in r.headers.items():
                if k.lower() in ("set-cookie", "location"):
                    print("HDR:", k, "=", v, flush=True)
            jar = parse_cookies(r.headers.getall("Set-Cookie", []))
            print("cookiesA:", jar, flush=True)

    # 方式B: 跟随重定向，从 session cookie jar 取
    print("\n--- 方式B: GET crossDomain (跟随重定向) ---", flush=True)
    async with aiohttp.ClientSession(headers=HEADERS) as s:
        async with s.get(url, allow_redirects=True) as r:
            print("status:", r.status, "final:", r.url, flush=True)
            for k, v in r.headers.items():
                if k.lower() == "set-cookie":
                    print("HDR:", k, "=", v, flush=True)
        jarB = {c.key: c.value for c in s.cookie_jar}
        print("jarB:", jarB, flush=True)

    cookies = {**jarB, **jar}
    print("\n合并 cookies:", cookies, flush=True)

    sessdata = cookies.get("SESSDATA", "")
    if not sessdata:
        print("仍未获取到 SESSDATA，请查看上面的诊断信息", flush=True)
        return

    with open(CRED_FILE, "w") as f:
        json.dump(
            {
                "sessdata": sessdata,
                "bili_jct": cookies.get("bili_jct", ""),
                "buvid3": cookies.get("buvid3", "") or "",
                "dedeuserid": cookies.get("DedeUserID", ""),
            },
            f,
        )
    print(f"登录成功！凭证已保存到 {CRED_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
