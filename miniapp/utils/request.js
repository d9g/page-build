/**
 * 网络请求封装
 * 自动携带 Token、统一错误处理
 * 支持 SSE 流式返回
 */
const { baseUrl, apiPrefix } = require('../config/api')

/**
 * 发起 HTTP 请求
 * @param {string} path API 路径（不含前缀）
 * @param {object} options 请求配置
 * @returns {Promise<object>} 响应数据
 */
function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    const token = getApp().globalData.token || ''
    const url = `${baseUrl}${apiPrefix}${path}`

    wx.request({
      url,
      method: options.method || 'GET',
      data: options.data || {},
      timeout: options.timeout || 180000,
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        ...(options.header || {}),
      },
      success(res) {
        if (res.statusCode === 200) {
          resolve(res.data)
        } else if (res.statusCode === 401) {
          wx.removeStorageSync('token')
          getApp().globalData.token = ''
          reject(new Error('登录已过期，请重新登录'))
        } else if (res.statusCode === 429) {
          reject(new Error(res.data.detail || '操作过于频繁，请稍后再试'))
        } else {
          const msg = res.data.detail || res.data.error || '请求失败'
          reject(new Error(msg))
        }
      },
      fail(err) {
        reject(new Error('网络异常，请检查网络连接'))
      },
    })
  })
}

/**
 * SSE 流式请求（用于排版）
 * @param {string} path API 路径
 * @param {object} data 请求数据
 * @param {function} onProgress 进度回调
 * @returns {Promise<object>} 最终结果
 */
function requestSSE(path, data, onProgress) {
  return new Promise((resolve, reject) => {
    const token = getApp().globalData.token || ''
    const url = `${baseUrl}${apiPrefix}${path}`

    // 微信小程序通过 enableChunked 支持流式接收
    const requestTask = wx.request({
      url,
      method: 'POST',
      data: data,
      enableChunked: true,
      timeout: 300000,
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        'Accept': 'text/event-stream',
      },
      success(res) {
        if (res.statusCode === 200 && res.data && res.data.sections) {
          resolve(res.data)
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络异常'))
      },
    })

    // 监听分块数据（SSE）
    requestTask.onChunkReceived((response) => {
      try {
        const chunk = ab2str(response.data)
        const lines = chunk.split('\n')
        
        for (const line of lines) {
          if (line.startsWith('data:')) {
            const dataStr = line.substring(5).trim()
            if (!dataStr) continue
            
            try {
              const parsedData = JSON.parse(dataStr)
              
              if (parsedData.status === 'processing' && onProgress) {
                onProgress(parsedData)
              }
              
              if (parsedData.sections) {
                resolve(parsedData)
              }
              
              if (parsedData.message && !parsedData.sections) {
                reject(new Error(parsedData.message))
              }
            } catch (e) {
              console.log('SSE chunk parse error:', e)
            }
          }
        }
      } catch (e) {
        console.log('SSE chunk error:', e)
      }
    })
  })
}

/**
 * ArrayBuffer 转 String
 */
function ab2str(buffer) {
  if (typeof buffer === 'object' && buffer.byteLength) {
    const buf = new Uint8Array(buffer)
    let str = ''
    for (let i = 0; i < buf.length; i++) {
      str += String.fromCharCode(buf[i])
    }
    return str
  }
  return buffer
}

/**
 * GET 请求
 */
function get(path, data) {
  return request(path, { method: 'GET', data })
}

/**
 * POST 请求
 */
function post(path, data) {
  return request(path, { method: 'POST', data })
}

/**
 * POST SSE 流式请求
 */
function postSSE(path, data, onProgress) {
  return requestSSE(path, data, onProgress)
}

module.exports = { request, get, post, postSSE }