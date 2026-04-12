/**
 * 网络请求封装
 * 自动携带 Token、统一错误处理
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
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        ...(options.header || {}),
      },
      success(res) {
        if (res.statusCode === 200) {
          resolve(res.data)
        } else if (res.statusCode === 401) {
          // Token 过期，需要重新登录
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

module.exports = { request, get, post }
