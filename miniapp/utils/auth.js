/**
 * 登录与认证管理
 */
const { post } = require('./request')

/**
 * 执行微信登录并获取后端 token
 * @returns {Promise<object>} 登录结果 {token, verified, quota}
 */
function login() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        if (!res.code) {
          reject(new Error('微信登录失败'))
          return
        }
        post('/auth/login', { code: res.code })
          .then(data => {
            // 保存 token
            getApp().globalData.token = data.token
            getApp().globalData.verified = data.verified
            wx.setStorageSync('token', data.token)
            resolve(data)
          })
          .catch(reject)
      },
      fail() {
        reject(new Error('微信登录失败'))
      },
    })
  })
}

/**
 * 检查登录状态，未登录则自动登录
 */
async function ensureLogin() {
  const app = getApp()
  if (app.globalData.token) {
    return
  }
  const cachedToken = wx.getStorageSync('token')
  if (cachedToken) {
    app.globalData.token = cachedToken
    return
  }
  await login()
}

module.exports = { login, ensureLogin }
