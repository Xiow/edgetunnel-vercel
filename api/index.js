// edgetunnel Vercel Function 入口（HTTP + WebSocket）
// 依赖：ws (npm)；Vercel 项目：api/index.js + _worker_node.js + vercel.json
// 环境变量：ADMIN=管理密码（必填）
import http from 'node:http';
import net from 'node:net';
import tls from 'node:tls';
import { WebSocketServer } from 'ws';
import edt from '../_worker_node.js';

// ---- request.fetcher.connect 模拟（CF Workers TCPSocket -> node:net / node:tls）----
function nodeConnect(options) {
  const { hostname, port } = options;
  let sock;
  if (options.tls || options.secureTransport === 'on') {
    sock = tls.connect({ host: hostname, port, servername: hostname });
  } else {
    sock = net.connect({ host: hostname, port });
  }
  let resolveOpened, rejectOpened, resolveClosed, rejectClosed;
  const opened = new Promise((res, rej) => { resolveOpened = res; rejectOpened = rej; });
  const closed = new Promise((res, rej) => { resolveClosed = res; rejectClosed = rej; });
  sock.on('connect', () => { try { resolveOpened(); } catch (e) {} });
  sock.on('secureConnect', () => { try { resolveOpened(); } catch (e) {} });
  sock.on('error', (e) => {
    try { rejectOpened(e); } catch (_) {}
    try { rejectClosed(e); } catch (_) {}
  });
  sock.on('close', () => { try { resolveClosed(); } catch (e) {} });
  const readable = new ReadableStream({
    start(controller) {
      sock.on('data', (chunk) => { try { controller.enqueue(new Uint8Array(chunk)); } catch (e) {} });
      sock.on('end', () => { try { controller.close(); } catch (e) {} });
      sock.on('close', () => { try { controller.close(); } catch (e) {} });
      sock.on('error', (e) => { try { controller.error(e); } catch (_) {} });
    },
    cancel() { try { sock.destroy(); } catch (e) {} }
  });
  const writable = new WritableStream({
    write(chunk) {
      return new Promise((res, rej) => {
        if (sock.destroyed) return rej(new Error('socket closed'));
        sock.write(Buffer.from(chunk), (err) => (err ? rej(err) : res()));
      });
    },
    close() { try { sock.end(); } catch (e) {} },
    abort() { try { sock.destroy(); } catch (e) {} }
  });
  return {
    opened, closed, readable, writable,
    close() { try { sock.destroy(); } catch (e) {} }
  };
}

function reqToRequest(req, bodyBuf) {
  const url = new URL(req.url, 'http://' + (req.headers.host || 'localhost'));
  const headers = {};
  for (const [k, v] of Object.entries(req.headers)) {
    headers[k] = Array.isArray(v) ? v.join(', ') : v;
  }
  const init = { method: req.method, headers };
  if (bodyBuf && bodyBuf.length) init.body = bodyBuf;
  const request = new Request(url, init);
  request.cf = { colo: 'NRT', asn: 0, asOrganization: '', city: '', country: '' };
  request.fetcher = { connect: nodeConnect };
  return request;
}

function readBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', () => resolve(Buffer.alloc(0)));
  });
}

const server = http.createServer(async (req, res) => {
  try {
    const bodyBuf = await readBody(req);
    const request = reqToRequest(req, bodyBuf);
    const response = await edt.fetch(request);
    const headers = {};
    for (const [k, v] of response.headers) headers[k] = v;
    res.writeHead(response.status, response.statusText || '', headers);
    if (response.body) {
      const buf = Buffer.from(await response.arrayBuffer());
      res.end(buf);
    } else {
      res.end();
    }
  } catch (e) {
    console.error('[http error]', e);
    try {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('Internal Server Error');
    } catch (_) {}
  }
});

// WebSocket（VLESS over WS）：Vercel 官方模式，wss 挂载在 server 上
const wss = new WebSocketServer({ server });
wss.on('connection', (ws, req) => {
  globalThis.__pendingWsSocket = ws;
  const request = reqToRequest(req, null);
  edt.fetch(request)
    .catch((e) => { console.error('[ws error]', e); try { ws.close(); } catch (_) {} })
    .finally(() => { globalThis.__pendingWsSocket = null; });
});

export default server;

// v2
