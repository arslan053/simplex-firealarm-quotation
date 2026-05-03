#!/usr/bin/env node
// Slack callback delivery helper.
// Runs outside n8n Code node Task Runner and performs the binary Slack upload flow.
const http = require('http');
const https = require('https');
const fs = require('fs');

const PORT = Number(process.env.SLACK_DELIVERY_HELPER_PORT || 3105);
const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://172.17.0.1:3001';
const LOGIN_EMAIL = process.env.RAGM_LOGIN_EMAIL || 'admin@acme.com';
const LOGIN_PASSWORD = process.env.RAGM_LOGIN_PASSWORD || 'admin123';

function parseUrl(s) {
  const m = String(s || '').match(/^(https?):\/\/([^\/:]+)(?::(\d+))?(\/.*)?$/);
  if (!m) return { protocol: 'https:', hostname: s, port: null, path: '/' };
  return { protocol: m[1] + ':', hostname: m[2], port: m[3] || null, path: m[4] || '/' };
}

function nativeRequest(method, reqUrl, headers, body) {
  return new Promise((resolve, reject) => {
    const opts = parseUrl(reqUrl);
    const mod = opts.protocol === 'https:' ? https : http;
    const req = mod.request({
      hostname: opts.hostname,
      port: opts.port,
      path: opts.path,
      method,
      headers: headers || {},
    }, (res) => {
      if ((res.statusCode === 301 || res.statusCode === 302) && res.headers.location) {
        nativeRequest(method, res.headers.location, headers, body).then(resolve).catch(reject);
        return;
      }
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve({ statusCode: res.statusCode, body: Buffer.concat(chunks) }));
    });
    req.on('error', reject);
    req.setTimeout(120000, () => { req.destroy(); reject(new Error('request timeout')); });
    if (body) req.write(body);
    req.end();
  });
}

function multipartBody(fields) {
  const boundary = '----ragmSlackComplete' + Date.now();
  const chunks = [];
  for (const [name, value] of Object.entries(fields)) {
    chunks.push(Buffer.from(
      '--' + boundary + '\r\n' +
      'Content-Disposition: form-data; name="' + name + '"\r\n\r\n' +
      String(value) + '\r\n'
    ));
  }
  chunks.push(Buffer.from('--' + boundary + '--\r\n'));
  return { boundary, body: Buffer.concat(chunks) };
}

async function sendSlackMessage(botToken, channelId, text) {
  const res = await nativeRequest('POST', 'https://slack.com/api/chat.postMessage', {
    Authorization: 'Bearer ' + botToken,
    'Content-Type': 'application/json',
  }, Buffer.from(JSON.stringify({ channel: channelId, text })));

  let data = {};
  try { data = JSON.parse(res.body.toString()); } catch (e) {}
  if (!data.ok) throw new Error('Slack message failed: ' + (data.error || 'unknown'));
}

async function getSlackFileInfo(botToken, fileId) {
  const res = await nativeRequest(
    'GET',
    'https://slack.com/api/files.info?file=' + encodeURIComponent(fileId),
    { Authorization: 'Bearer ' + botToken },
    null
  );
  const data = JSON.parse(res.body.toString());
  if (!data.ok) throw new Error('Slack files.info failed: ' + (data.error || 'unknown'));
  return data.file || {};
}

function fileIsSharedTo(file, channelId) {
  const channels = []
    .concat(file.channels || [])
    .concat(file.groups || [])
    .concat(file.ims || []);
  if (channels.includes(channelId)) return true;

  const shares = file.shares || {};
  for (const shareGroup of Object.values(shares)) {
    for (const [sharedChannelId] of Object.entries(shareGroup || {})) {
      if (sharedChannelId === channelId) return true;
    }
  }
  return false;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForSlackFileShare(botToken, fileId, channelId) {
  let fileInfo = {};
  for (let attempt = 0; attempt < 8; attempt += 1) {
    fileInfo = await getSlackFileInfo(botToken, fileId);
    if (fileIsSharedTo(fileInfo, channelId)) return fileInfo;
    await sleep(1000);
  }
  return fileInfo;
}

function resetSlackConversation(userId) {
  if (!userId) return;
  try {
    const convPath = '/home/node/.n8n/slack_conversations.json';
    const convs = JSON.parse(fs.readFileSync(convPath, 'utf8'));
    if (convs[userId]) {
      convs[userId] = { state: 'new' };
      fs.writeFileSync(convPath, JSON.stringify(convs), 'utf8');
    }
  } catch (e) {}
}

async function deliver(params) {
  const {
    project_id,
    tenant_slug,
    channel_id,
    bot_token,
    user_id,
    file_name,
    status,
    error_step,
    error_message,
  } = params;

  if (!channel_id || !bot_token) {
    return { delivered: false, reason: 'missing channel_id or bot_token' };
  }

  try {
    if (status === 'completed' && project_id) {
      const tenantSlug = tenant_slug || 'acme';

      const loginRes = await nativeRequest('POST', BACKEND_API_URL + '/api/auth/login', {
        'Content-Type': 'application/json',
        'x-tenant-slug': tenantSlug,
      }, Buffer.from(JSON.stringify({ email: LOGIN_EMAIL, password: LOGIN_PASSWORD })));
      const loginData = JSON.parse(loginRes.body.toString());
      if (!loginData.access_token) throw new Error('Login failed');

      const dlRes = await nativeRequest('GET',
        BACKEND_API_URL + '/api/projects/' + project_id + '/quotation/download-file?format=docx',
        { Authorization: 'Bearer ' + loginData.access_token, 'x-tenant-slug': tenantSlug },
        null
      );
      if (dlRes.statusCode !== 200) throw new Error('Download failed HTTP ' + dlRes.statusCode);

      const fileData = dlRes.body;
      const fname = file_name || 'quotation.docx';
      const getUrlRes = await nativeRequest(
        'POST',
        'https://slack.com/api/files.getUploadURLExternal?filename=' +
          encodeURIComponent(fname) + '&length=' + fileData.length,
        { Authorization: 'Bearer ' + bot_token },
        null
      );
      const getUrlData = JSON.parse(getUrlRes.body.toString());
      if (!getUrlData.ok) throw new Error('Slack getUploadURL failed: ' + (getUrlData.error || 'unknown'));

      const uploadRes = await nativeRequest('POST', getUrlData.upload_url, {
        'Content-Type': 'application/octet-stream',
        'Content-Length': String(fileData.length),
      }, fileData);
      if (uploadRes.statusCode >= 400) throw new Error('Slack upload failed HTTP ' + uploadRes.statusCode);

      const completeForm = multipartBody({
        files: JSON.stringify([{ id: getUrlData.file_id, title: fname }]),
        channel_id,
        initial_comment: 'Your quotation is ready!',
      });
      const completeRes = await nativeRequest('POST', 'https://slack.com/api/files.completeUploadExternal', {
        Authorization: 'Bearer ' + bot_token,
        'Content-Type': 'multipart/form-data; boundary=' + completeForm.boundary,
        'Content-Length': String(completeForm.body.length),
      }, completeForm.body);
      const completeData = JSON.parse(completeRes.body.toString());
      if (!completeData.ok) throw new Error('Slack completeUpload failed: ' + (completeData.error || 'unknown'));

      const fileInfo = await waitForSlackFileShare(bot_token, getUrlData.file_id, channel_id);
      if (!fileIsSharedTo(fileInfo, channel_id)) {
        throw new Error('Slack upload completed but file was not shared to channel ' + channel_id);
      }

      resetSlackConversation(user_id);
      return { delivered: true, platform: 'slack', file_id: getUrlData.file_id };
    }

    if (status === 'failed') {
      await sendSlackMessage(
        bot_token,
        channel_id,
        'Quotation generation failed.\nStep: ' + (error_step || 'unknown') +
          '\nError: ' + (error_message || 'unknown')
      );
      resetSlackConversation(user_id);
      return { delivered: true, platform: 'slack', status: 'error_notified' };
    }

    return { delivered: false, reason: 'unsupported status: ' + (status || 'unknown') };
  } catch (err) {
    try {
      await sendSlackMessage(bot_token, channel_id, 'Could not deliver quotation: ' + (err.message || String(err)));
    } catch (e) {}
    resetSlackConversation(user_id);
    return { delivered: false, error: err.message || String(err) };
  }
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString() || '{}')); }
      catch (err) { reject(err); }
    });
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  if (req.method !== 'POST' || req.url !== '/deliver') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: false, error: 'not found' }));
    return;
  }

  try {
    const params = await readJsonBody(req);
    const result = await deliver(params);
    res.writeHead(result.delivered ? 200 : 502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(result));
  } catch (err) {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ delivered: false, error: err.message || String(err) }));
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('Slack delivery helper listening on 127.0.0.1:' + PORT);
});
