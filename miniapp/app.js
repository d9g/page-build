/**
 * 小程序入口
 * 全局登录、token 管理、版本更新检测
 */
const { login } = require('./utils/auth')
const { get } = require('./utils/request')

App({
  globalData: {
    token: '',
    verified: false,
    userInfo: null,
    layoutContent: '',
  },

  onLaunch() {
    // 版本更新检测
    this.checkUpdate()

    // 尝试从缓存恢复 token
    const cachedToken = wx.getStorageSync('token')
    if (cachedToken) {
      this.globalData.token = cachedToken
    }

    // 自动登录并恢复验证状态
    login()
      .then(data => {
        console.log('登录成功', data)
        // 登录成功后从后端恢复 verified 状态，避免冷启动后丢失
        return get('/user/status')
      })
      .then(status => {
        this.globalData.verified = status.verified
      })
      .catch(err => {
        console.warn('自动登录或状态恢复失败，用户操作时再处理', err)
      })
  },

  /** 小程序版本更新检测 */
  checkUpdate() {
    if (!wx.canIUse('getUpdateManager')) return
    const updateManager = wx.getUpdateManager()
    updateManager.onUpdateReady(() => {
      wx.showModal({
        title: '更新提示',
        content: '新版本已经准备好，是否重启小程序？',
        success: (res) => {
          if (res.confirm) {
            updateManager.applyUpdate()
          }
        },
      })
    })
  },
})
