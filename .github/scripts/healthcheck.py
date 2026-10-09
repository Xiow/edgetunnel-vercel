#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CF鑺傜偣璁㈤槄鍏ㄨ嚜鍔ㄥ仴搴锋鏌ワ紙GitHub Actions 浜戠鎵ц锛?妫€鏌ラ」锛?  1. 璁㈤槄鍙敤锛欻TTP 200锛岃妭鐐规暟 >= 8锛屼笖鍏ㄩ儴涓虹洿杩炲湴鍧€锛堟棤 CF 闅忔満浼橀€?IP锛?  2. 鍚庡彴 /login 杩斿洖瀹屾暣 HTML
  3. 鏍硅矾寰勮繑鍥?nginx 浼椤?寮傚父鏃惰嚜鍔ㄥ鐞嗭細
  - POST Vercel Deploy Hook 瑙﹀彂鐢熶骇閮ㄧ讲锛堟棤闇€ API token锛?  - 绛夊緟璁㈤槄鎭㈠鍚庡楠?"""
import urllib.request
import urllib.parse
import json
import re
import os
import sys
import time
import gzip

SUB_URL = os.environ.get('SUB_URL', '')
DEPLOY_HOOK_URL = os.environ.get('DEPLOY_HOOK_URL', '')
BASE = 'https://www.xiow123.duckdns.org'

ALLOWED_SERVERS = {
    'www.xiow123.duckdns.org',
    '76.76.21.21',
    'edgetunnel-vercel-orcin.vercel.app',
}


def fetch(url, ua='Mozilla/5.0', timeout=40):
    req = urllib.request.Request(url, headers={'User-Agent': ua, 'Accept-Encoding': 'gzip'})
    resp = urllib.request.urlopen(req, timeout=timeout)
    data = resp.read()
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    return resp.status, data


def parse_nodes(text):
    """浠?Clash YAML 瑙ｆ瀽鑺傜偣 (name, server) 鍒楄〃"""
    nodes = []
    if 'proxies:' in text:
        proxies_section = text.split('proxies:')[1] if 'proxies:' in text else text
        # 鍖归厤鍗曡鏍煎紡: {name: X, server: Y, port: N, type: vless, ...}
        for m in re.finditer(r'\{name:\s*([^,]+),\s*server:\s*([^,\s}]+)', proxies_section):
            nodes.append((m.group(1).strip(), m.group(2).strip()))
        if not nodes:
            # 鍏煎澶氳鏍煎紡
            names = re.findall(r'name:\s*([^,]+),', proxies_section)
            servers = re.findall(r'server:\s*([^,\s}]+)', proxies_section)
            for n, s in zip(names, servers):
                nodes.append((n.strip(), s.strip()))
    else:
        # vless:// 鏄庢枃
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('vless://'):
                m = re.search(r'@([^:]+):(\d+)', line)
                if m:
                    nodes.append((line[:30], m.group(1)))
    # 杩囨护 DNS 閰嶇疆骞叉壈
    return [(n, s) for n, s in nodes if s and '.' in s and not s.startswith('-')]


def trigger_deploy_hook():
    """POST Vercel Deploy Hook 瑙﹀彂鐢熶骇閮ㄧ讲"""
    if not DEPLOY_HOOK_URL:
        print('  鏈厤缃?DEPLOY_HOOK_URL')
        return False
    try:
        req = urllib.request.Request(DEPLOY_HOOK_URL, method='POST')
        resp = urllib.request.urlopen(req, timeout=40)
        body = resp.read().decode('utf-8', errors='ignore')
        print('  Deploy Hook HTTP %s: %s' % (resp.status, body[:200]))
        return resp.status == 200
    except Exception as e:
        print('  Deploy Hook 瑙﹀彂澶辫触: %s' % e)
        return False


def wait_sub_ok(timeout=360):
    """杞璁㈤槄鐩村埌鎭㈠姝ｅ父锛堥儴缃插畬鎴愶級"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            status, data = fetch(SUB_URL, 'clash-verge/2.0.0')
            text = data.decode('utf-8', errors='ignore')
            nodes = parse_nodes(text)
            servers = [s for _, s in nodes]
            bad = [s for s in servers if s not in ALLOWED_SERVERS]
            ok = status == 200 and len(nodes) >= 8 and len(bad) == 0
            print('  杞: HTTP %s, 鑺傜偣鏁?%d, 闈炴硶=%d' % (status, len(nodes), len(bad)))
            if ok:
                return True
        except Exception as e:
            print('  杞鎷夊彇澶辫触: %s' % e)
        time.sleep(30)
    return False


def main():
    results = []
    all_ok = True

    # 1. 璁㈤槄妫€鏌?    print('[1] 璁㈤槄鍋ュ悍妫€鏌?)
    try:
        status, data = fetch(SUB_URL, 'clash-verge/2.0.0')
        text = data.decode('utf-8', errors='ignore')
        nodes = parse_nodes(text)
        servers = [s for _, s in nodes]
        n = len(nodes)
        bad = [s for s in servers if s not in ALLOWED_SERVERS]
        ok = status == 200 and n >= 8 and len(bad) == 0
        print('  HTTP %s, 鑺傜偣鏁?%d, 闈炴硶server=%d' % (status, n, len(bad)))
        if bad:
            print('  闈炴硶server绀轰緥:', bad[:3])
        results.append(('璁㈤槄姝ｅ父(鈮?鑺傜偣涓旂洿杩?', ok))
        all_ok = all_ok and ok
    except Exception as e:
        print('  璁㈤槄鎷夊彇澶辫触: %s' % e)
        results.append(('璁㈤槄姝ｅ父(鈮?鑺傜偣涓旂洿杩?', False))
        all_ok = False

    # 2. 鍚庡彴鐧诲綍椤?    print('[2] 鍚庡彴 /login 妫€鏌?)
    try:
        status, data = fetch(BASE + '/login')
        text = data.decode('utf-8', errors='ignore')
        ok = status == 200 and ('<!DOCTYPE html>' in text[:80] or '鐧诲綍璁剧疆椤甸潰' in text)
        print('  HTTP %s, %d 瀛楄妭, HTML=%s' % (status, len(data), ok))
        results.append(('鍚庡彴/login瀹屾暣HTML', ok))
        all_ok = all_ok and ok
    except Exception as e:
        print('  鍚庡彴妫€鏌ュけ璐? %s' % e)
        results.append(('鍚庡彴/login瀹屾暣HTML', False))
        all_ok = False

    # 3. 鏍硅矾寰勪吉瑁呴〉
    print('[3] 鏍硅矾寰勪吉瑁呴〉妫€鏌?)
    try:
        status, data = fetch(BASE + '/')
        ok = status == 200 and b'Welcome to nginx' in data
        print('  HTTP %s, %d 瀛楄妭, nginx浼=%s' % (status, len(data), ok))
        results.append(('鏍硅矾寰刵ginx浼椤?, ok))
        all_ok = all_ok and ok
    except Exception as e:
        print('  鏍硅矾寰勬鏌ュけ璐? %s' % e)
        results.append(('鏍硅矾寰刵ginx浼椤?, False))
        all_ok = False

    print()
    for name, ok in results:
        print('  %s %s' % ('PASS' if ok else 'FAIL', name))

    if all_ok:
        print('\nOK: 鍋ュ悍妫€鏌ュ叏閮ㄩ€氳繃')
        return 0

    # 鑷姩淇锛氳Е鍙?Deploy Hook 閲嶆柊閮ㄧ讲
    print('\nWARN: 瀛樺湪寮傚父锛孭OST Deploy Hook 瑙﹀彂閲嶆柊閮ㄧ讲...')
    if not trigger_deploy_hook():
        print('FAIL: Deploy Hook 瑙﹀彂澶辫触')
        return 1
    print('宸茶Е鍙戦噸鏂伴儴缃诧紝绛夊緟璁㈤槄鎭㈠锛堟渶闀?6 鍒嗛挓锛?..')
    if wait_sub_ok():
        print('OK: 鑷姩淇鎴愬姛锛岃闃呭凡鎭㈠鐩磋繛鑺傜偣')
        return 0
    else:
        print('FAIL: 绛夊緟璁㈤槄鎭㈠瓒呮椂锛岄渶瑕佷汉宸ヤ粙鍏?)
        return 1


if __name__ == '__main__':
    sys.exit(main())
