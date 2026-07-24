# -*- coding: utf-8 -*-
"""
股票查询结果页 API
GET /stock/{task_id}        → HTML 结果页（粉丝点击链接打开）
GET /api/v1/stock/{task_id}/status → JSON 任务状态（前端轮询）
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from services.stock_task_service import get_task

logger = logging.getLogger(__name__)
router = APIRouter(tags=["股票查询"])


# ==================== 结果页 HTML（移动端适配，内联避免额外静态文件）====================
_RESULT_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>AI 股票评分</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; -webkit-font-smoothing: antialiased; }
.container { max-width: 480px; margin: 0 auto; padding: 16px; min-height: 100vh; }
.loading { text-align: center; padding: 60px 20px; }
.spinner { width: 40px; height: 40px; border: 3px solid #e0e0e0; border-top-color: #1890ff; border-radius: 50%; margin: 0 auto 16px; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { color: #666; font-size: 14px; line-height: 1.8; }
.stock-code { font-size: 20px; font-weight: 600; color: #1890ff; margin-bottom: 8px; }
.card { background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.score-row { display: flex; gap: 12px; margin-bottom: 16px; }
.score-box { flex: 1; background: #f9f9f9; border-radius: 8px; padding: 14px 8px; text-align: center; }
.score-label { font-size: 12px; color: #999; margin-bottom: 6px; }
.score-val { font-size: 28px; font-weight: 700; line-height: 1; }
.tag { font-size: 13px; font-weight: 600; }
.dim-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.dim-item { background: #fafafa; border-radius: 8px; padding: 12px; }
.dim-head { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; font-size: 13px; color: #333; }
.dim-val { font-size: 18px; font-weight: 700; }
.dim-desc { font-size: 11px; color: #999; }
.report { background: #fafafa; border-radius: 8px; padding: 14px; font-size: 13px; color: #555; line-height: 1.8; white-space: pre-wrap; }
.trap-box { border-radius: 8px; padding: 14px; margin-bottom: 16px; border-left: 4px solid; }
.trap-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.trap-reasons { background: rgba(255,255,255,0.7); border-radius: 4px; padding: 8px 10px; font-size: 12px; line-height: 1.7; }
.kbar-box { border-radius: 8px; padding: 14px; margin-bottom: 16px; border-left: 4px solid; }
.kbar-title { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.kbar-data { font-size: 12px; color: #666; }
.disclaimer { text-align: center; font-size: 11px; color: #999; padding: 16px; line-height: 1.6; }
.error-box { text-align: center; padding: 40px 20px; }
.error-icon { font-size: 40px; margin-bottom: 12px; }
.error-msg { color: #ff4d4f; font-size: 14px; line-height: 1.6; margin-bottom: 16px; }
.btn-retry { display: inline-block; padding: 8px 24px; background: #1890ff; color: #fff; border: none; border-radius: 20px; font-size: 13px; }
.section-title { font-size: 14px; font-weight: 600; color: #333; margin-bottom: 10px; }
.refresh-hint { font-size: 11px; color: #999; text-align: center; margin-top: 8px; }
</style>
</head>
<body>
<div class="container" id="app">
  <div class="loading">
    <div class="spinner"></div>
    <div class="stock-code" id="stockCode"></div>
    <div class="loading-text">AI 正在分析中...<br>预计 10 秒，请稍候</div>
  </div>
</div>
<script>
const TASK_ID = window.location.pathname.split('/').filter(Boolean).pop();
let pollCount = 0;
const MAX_POLLS = 40;

function colorFor(v) { return v >= 70 ? '#52c41a' : v >= 50 ? '#faad14' : '#ff4d4f'; }

async function poll() {
  try {
    const resp = await fetch('/api/v1/stock/' + TASK_ID + '/status');
    const data = await resp.json();
    if (data.code !== 0 || !data.data) {
      renderNotFound();
      return;
    }
    const task = data.data;
    if (task.status === 'done' && task.result) {
      renderResult(task);
      return;
    } else if (task.status === 'error') {
      renderError(task.error || '评估失败');
      return;
    }
    document.getElementById('stockCode').textContent = task.stock_code || '';
    pollCount++;
    if (pollCount < MAX_POLLS) {
      setTimeout(poll, 3000);
    } else {
      renderError('查询超时，请重新发送股票代码');
    }
  } catch (e) {
    renderError('网络异常：' + e.message);
  }
}

function renderResult(task) {
  const d = task.result;
  const score = parseFloat(d.ai_score) || 0;
  const sc = colorFor(score);
  const riskText = d.ai_risk_level === 'low' ? '低风险' : d.ai_risk_level === 'medium' ? '中风险' : d.ai_risk_level === 'high' ? '高风险' : '-';
  const rc = d.ai_risk_level === 'low' ? '#52c41a' : d.ai_risk_level === 'medium' ? '#faad14' : '#ff4d4f';
  let html = '<div class="stock-code">' + (d.stock_name || d.stock_code || '') + ' (' + (d.stock_code || '') + ')</div>';
  html += '<div class="card">';
  html += '<div class="score-row">';
  html += '<div class="score-box" style="border-left:3px solid ' + sc + ';"><div class="score-label">综合评分</div><div class="score-val" style="color:' + sc + ';">' + (d.ai_score != null ? score.toFixed(1) : '-') + '</div></div>';
  html += '<div class="score-box" style="border-left:3px solid #1890ff;"><div class="score-label">信号等级</div><div class="tag" style="color:#1890ff;padding-top:8px;">' + (d.ai_label || '-') + '</div></div>';
  html += '<div class="score-box" style="border-left:3px solid ' + rc + ';"><div class="score-label">风险等级</div><div class="tag" style="color:' + rc + ';padding-top:8px;">' + riskText + '</div></div>';
  html += '</div>';
  const dims = [
    {label:'技术面', val:d.technical_score, icon:'📈', desc:'均线/RSI/MACD'},
    {label:'基本面', val:d.fundamental_score, icon:'💰', desc:'市值/PE/营收'},
    {label:'情绪面', val:d.sentiment_score, icon:'🔥', desc:'连板/温度/竞价'},
    {label:'风控', val:d.risk_score, icon:'🛡️', desc:'ST/回撤/流动性'}
  ];
  html += '<div class="dim-grid">';
  for (let i = 0; i < dims.length; i++) {
    const dm = dims[i];
    const v = dm.val != null ? parseFloat(dm.val) : null;
    html += '<div class="dim-item">';
    html += '<div class="dim-head"><span>' + dm.icon + '</span><span>' + dm.label + '</span></div>';
    html += '<div class="dim-val" style="color:' + (v != null ? colorFor(v) : '#999') + ';">' + (v != null ? v.toFixed(1) : '-') + '</div>';
    html += '<div class="dim-desc">' + dm.desc + '</div>';
    html += '</div>';
  }
  html += '</div>';
  if (d.trap_score != null && d.trap_score >= 30) {
    const tl = d.trap_level || 'warning';
    const tc = tl === 'danger' ? '#ff4d4f' : '#faad14';
    const tb = tl === 'danger' ? '#fff1f0' : '#fffbe6';
    const tt = tl === 'danger' ? '🔴 诱多预警' : '🟡 诱多提示';
    html += '<div class="trap-box" style="background:' + tb + ';border-color:' + tc + ';">';
    html += '<div class="trap-title" style="color:' + tc + ';">' + tt + '（危险分 ' + d.trap_score + '）</div>';
    if (d.trap_reasons) {
      let reasons = d.trap_reasons;
      try { reasons = JSON.parse(reasons); } catch(e) {}
      if (Array.isArray(reasons) && reasons.length) {
        html += '<div class="trap-reasons">';
        for (let r = 0; r < reasons.length; r++) { html += '<div>• ' + reasons[r] + '</div>'; }
        html += '</div>';
      }
    }
    html += '</div>';
  }
  if (d.kbar_kup2 != null || d.kbar_klow2 != null) {
    const kup = d.kbar_kup2 != null && d.kbar_kup2 !== '' ? parseFloat(d.kbar_kup2) : null;
    const klow = d.kbar_klow2 != null && d.kbar_klow2 !== '' ? parseFloat(d.kbar_klow2) : null;
    if (kup != null || klow != null) {
      html += '<div class="kbar-box" style="background:#f0f5ff;border-color:#1890ff;">';
      html += '<div class="kbar-title">📐 KBar 形态</div>';
      html += '<div class="kbar-data">上影 KUP2=<strong>' + (kup != null ? kup.toFixed(3) : '-') + '</strong> 下影 KLOW2=<strong>' + (klow != null ? klow.toFixed(3) : '-') + '</strong></div>';
      html += '</div>';
    }
  }
  if (d.report) {
    html += '<div class="section-title">📋 评估报告</div>';
    html += '<div class="report">' + d.report + '</div>';
  }
  html += '</div>';
  html += '<div class="refresh-hint">数据仅供参考 · 评分时间：' + (d.refreshed_at || task.done_at || '') + '</div>';
  html += '<div class="disclaimer">⚠️ 本数据由 AI 模型根据公开市场数据计算，仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。</div>';
  document.getElementById('app').innerHTML = html;
  window.scrollTo(0, 0);
}

function renderError(msg) {
  document.getElementById('app').innerHTML =
    '<div class="error-box"><div class="error-icon">😕</div>' +
    '<div class="error-msg">' + msg + '</div>' +
    '<div style="color:#999;font-size:12px;margin-bottom:16px;">请重新在公众号发送股票代码</div></div>' +
    '<div class="disclaimer">⚠️ 本数据仅供参考，不构成投资建议。</div>';
}

function renderNotFound() {
  document.getElementById('app').innerHTML =
    '<div class="error-box"><div class="error-icon">⏰</div>' +
    '<div class="error-msg">查询链接已过期</div>' +
    '<div style="color:#999;font-size:12px;">请重新在公众号发送股票代码获取新链接</div></div>' +
    '<div class="disclaimer">⚠️ 本数据仅供参考，不构成投资建议。</div>';
}

poll();
</script>
</body>
</html>"""


@router.get("/stock/{task_id}", response_class=HTMLResponse)
async def stock_result_page(task_id: str):
    """股票查询结果页（粉丝点击公众号回复的链接打开）"""
    return _RESULT_PAGE_HTML


@router.get("/api/v1/stock/{task_id}/status")
async def stock_task_status(task_id: str, request: Request):
    """查询任务状态（前端轮询用）

    返回:
        {"code": 0, "data": {task_id, stock_code, status, result, error, ...}}
        status: pending / done / error
    """
    redis_client = getattr(request.app.state, "redis", None)
    task = await get_task(task_id, redis_client)
    if not task:
        return JSONResponse(
            {"code": 404, "message": "任务不存在或已过期", "data": None},
            status_code=404,
        )
    return JSONResponse({"code": 0, "data": task})
