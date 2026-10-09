

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
              text = data.decode('utf-8', errors='ignore')
              ok = status == 200 and ('<!DOCTYPE html>' in text[:80] or '登录设置页面' in text)
              print('  HTTP %s, %d 字节, HTML=%s' % (status, len(data), ok))
              results.append(('后台/login完整HTML', ok))
              all_ok = all_ok and ok
except Exception as e:
          print('  后台检查失败: %s' % e)
          results.append(('后台/login完整HTML', False))
          all_ok = False

    # 3. 根路径伪装页
      print('[3] 根路径伪装页检查')
    try:
              status, data = fetch(BASE + '/')
              ok = status == 200 and b'Welcome to nginx' in data
              print('  HTTP %s, %d 字节, nginx伪装=%s' % (status, len(data), ok))
              results.append(('根路径nginx伪装页', ok))
              all_ok = all_ok and ok
except Exception as e:
          print('  根路径检查失败: %s' % e)
          results.append(('根路径nginx伪装页', False))
          all_ok = False

    # 4. Vercel 部署状态
      print('[4] Vercel 生产部署状态检查')
    try:
              data = json.loads(vercel_api('/v6/deployments?projectId=%s&limit=1&state=READY&rollback=0' % urllib.parse.quote(VERCEL_PROJECT_ID)))
              deps = data.get('deployments', [])
              ok = len(deps) > 0
              print('  READY 部署数: %d' % len(deps))
              results.append(('Vercel部署Ready', ok))
              all_ok = all_ok and ok
except Exception as e:
          print('  Vercel API 失败: %s' % e)
          results.append(('Vercel部署Ready', False))
          all_ok = False

    print()
    for name, ok in results:
              print('  %s %s' % ('✅' if ok else '❌', name))

    if all_ok:
              print('\n✅ 健康检查全部通过')
              return 0

    # 自动修复：触发 Redeploy
    print('\n⚠️ 存在异常，触发 Vercel Redeploy 自动修复...')
    try:
              uid = get_latest_deployment()
              if not uid:
                            print('  ❌ 未找到 READY 部署，无法 Redeploy')
                            return 1
                        print('  最新部署 uid=%s' % uid)
        redeploy(uid)
        print('  ✅ Redeploy 已触发，等待部署完成...')
        if wait_deploy_ready(uid):
                      print('  部署已完成，复验中...')
                      try:
                                        status, data = fetch(SUB_URL, 'clash-verge/2.0.0')
                                        text = data.decode('utf-8', errors='ignore')
                                        nodes = parse_nodes(text)
                                        servers = [s for _, s in nodes]
                                        bad = [s for s in servers if s not in ALLOWED_SERVERS]
                                        ok = status == 200 and len(nodes) >= 8 and len(bad) == 0
                                        print('  复验: HTTP %s, 节点数=%d, 非法=%d' % (status, len(nodes), len(bad)))
                                        if ok:
                                                              print('  ✅ 自动修复成功，订阅恢复正常')
                                                              return 0
                      else:
                                            print('  ❌ 复验仍异常，需要人工介入')
                                            return 1
except Exception as e:
                print('  ❌ 复验失败: %s' % e)
                return 1
else:
            print('  ❌ 部署等待超时')
            return 1
except Exception as e:
        print('  ❌ Redeploy 失败: %s' % e)
        return 1


if __name__ == '__main__':
      sys.exit(main())
