import os, re, sys, time, urllib.request, json, urllib.error

SUB_URL = os.environ.get('SUB_URL', '')
VERCEL_TOKEN = os.environ.get('VERCEL_TOKEN', '')
VERCEL_PROJECT_ID = os.environ.get('VERCEL_PROJECT_ID', '')

BASE = 'https://www.xiow123.duckdns.org'
ALLOWED_SERVERS = {
    'www.xiow123.duckdns.org',
    '76.76.21.21',
    'edgetunnel-vercel-orcin.vercel.app',
}

def fetch(url, ua='Mozilla/5.0'):
    req = urllib.request.Request(url, headers={'User-Agent': ua})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()

def parse_nodes(text):
    nodes = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(('vless://', 'vmess://', 'trojan://')):
            continue
        if line.startswith('vless://'):
            try:
                host = line.split('@', 1)[1].split(':', 1)[0]
            except Exception:
                host = 'unknown'
        else:
            host = 'unknown'
        nodes.append((line, host))
    return nodes

def vercel_ready():
    try:
        req = urllib.request.Request(
            'https://api.vercel.com/v13/deployments?projectId=%s&limit=1&state=READY' % VERCEL_PROJECT_ID,
            headers={'Authorization': 'Bearer %s' % VERCEL_TOKEN})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode('utf-8'))
            return bool(data.get('deployments'))
    except Exception as e:
        print('  Vercel READY 查询失败: %s' % e)
        return None

def redeploy():
    try:
        req = urllib.request.Request(
            'https://api.vercel.com/v13/deployments?projectId=%s&limit=1&state=READY' % VERCEL_PROJECT_ID,
            headers={'Authorization': 'Bearer %s' % VERCEL_TOKEN})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode('utf-8'))
            ds = data.get('deployments', [])
        if not ds:
            print('  无 READY 部署可触发 redeploy')
            return False
        uid = ds[0]['uid']
        req2 = urllib.request.Request(
            'https://api.vercel.com/v13/deployments/%s/redeploy' % uid,
            data=b'{}', method='POST',
            headers={'Authorization': 'Bearer %s' % VERCEL_TOKEN, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req2, timeout=30) as r:
            status = r.status
        print('  Redeploy 触发成功 (HTTP %s), uid=%s' % (status, uid))
        return True
    except Exception as e:
        print('  Redeploy 失败: %s' % e)
        return False

def wait_ready(seconds=300):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if vercel_ready():
            return True
        time.sleep(20)
    return False

def main():
    results = []
    all_ok = True

    # 1. 订阅检查
    print('[1] 订阅健康检查')
    try:
        status, data = fetch(SUB_URL, 'clash-verge/2.0.0')
        text = data.decode('utf-8', errors='ignore')
        nodes = parse_nodes(text)
        servers = [s for _, s in nodes]
        n = len(nodes)
        bad = [s for s in servers if s not in ALLOWED_SERVERS]
        ok = status == 200 and n >= 8 and len(bad) == 0
        print('  HTTP %s, 节点数=%d, 非法server=%d' % (status, n, len(bad)))
        if bad:
            print('  非法server示例:', bad[:3])
        results.append(('订阅正常(>=8节点且直连)', ok))
        all_ok = all_ok and ok
    except Exception as e:
        print('  订阅拉取失败: %s' % e)
        results.append(('订阅正常(>=8节点且直连)', False))
        all_ok = False

    # 2. 后台登录页
    print('[2] 后台 /login 检查')
    try:
        status, data = fetch(BASE + '/login')
        body = data.decode('utf-8', errors='ignore')
        ok = status == 200 and len(data) > 20000 and 'login' in body.lower()
        print('  HTTP %s, 大小=%d 字节' % (status, len(data)))
        results.append(('后台 /login 正常', ok))
        all_ok = all_ok and ok
    except Exception as e:
        print('  后台 /login 拉取失败: %s' % e)
        results.append(('后台 /login 正常', False))
        all_ok = False

    # 3. 根路径伪装页
    print('[3] 根路径 nginx 伪装检查')
    try:
        status, data = fetch(BASE + '/')
        body = data.decode('utf-8', errors='ignore')
        ok = status == 200 and 'nginx' in body.lower()
        print('  HTTP %s, 大小=%d 字节, nginx=%s' % (status, len(data), 'nginx' in body.lower()))
        results.append(('根路径 nginx 伪装', ok))
        all_ok = all_ok and ok
    except Exception as e:
        print('  根路径检查失败: %s' % e)
        results.append(('根路径 nginx 伪装', False))
        all_ok = False

    # 4. Vercel 部署状态
    print('[4] Vercel 部署状态检查')
    ready = vercel_ready()
    if ready is None:
        results.append(('Vercel READY 部署', False))
        all_ok = False
    elif ready:
        print('  Vercel 有 READY 部署')
        results.append(('Vercel READY 部署', True))
    else:
        print('  Vercel 无 READY 部署')
        results.append(('Vercel READY 部署', False))
        all_ok = False

    # 输出结果
    print('\n=== 健康检查结果 ===')
    for name, ok in results:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', name))
    print('=== 总体: %s ===' % ('全部通过' if all_ok else '存在异常'))

    if all_ok:
        print('OK: 全部健康')
        sys.exit(0)
    else:
        print('异常: 触发自动 Redeploy 修复')
        if redeploy():
            print('等待 Vercel 重新部署完成...')
            if wait_ready():
                print('Redeploy 完成，重新验证订阅...')
                try:
                    status, data = fetch(SUB_URL, 'clash-verge/2.0.0')
                    text = data.decode('utf-8', errors='ignore')
                    nodes = parse_nodes(text)
                    print('  复验: HTTP %s, 节点数=%d' % (status, len(nodes)))
                    if status == 200 and len(nodes) >= 8:
                        print('OK: 复验通过')
                        sys.exit(0)
                    else:
                        print('FAIL: 复验未通过')
                        sys.exit(1)
                except Exception as e:
                    print('复验拉取失败: %s' % e)
                    sys.exit(1)
            else:
                print('FAIL: 等待 Redeploy 完成超时')
                sys.exit(1)
        else:
            print('FAIL: 自动修复触发失败')
            sys.exit(1)

if __name__ == '__main__':
    main()
