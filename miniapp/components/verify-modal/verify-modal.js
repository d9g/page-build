/**
 * 关注验证弹窗组件
 * 展示当前推广的单个公众号，用户输入验证码完成校验
 */
const { get, post } = require('../../utils/request')

Component({
  properties: {
    show: { type: Boolean, value: false },
  },

  data: {
    account: {},
    keyword: '排版',
    validDays: 30,
    code: '',
    verifying: false,
  },

  observers: {
    'show': function (val) {
      if (val) this.loadActiveAccount()
    },
  },

  methods: {
    /** 加载当前推广的公众号 */
    async loadActiveAccount() {
      try {
        const res = await get('/accounts/active')
        this.setData({
          account: res.account || {},
          keyword: res.keyword || '排版',
          validDays: res.verify_valid_days || 30,
        })
      } catch (err) {
        console.error('加载公众号信息失败', err)
      }
    },

    /** 验证码输入 */
    onCodeInput(e) {
      this.setData({ code: e.detail.value })
    },

    /** 提交验证 */
    async onVerify() {
      if (this.data.code.length !== 4 || this.data.verifying) return
      this.setData({ verifying: true })

      try {
        const res = await post('/verify', { code: this.data.code })
        if (res.success) {
          this.triggerEvent('verified')
        } else {
          wx.showToast({ title: res.message || '验证失败', icon: 'none' })
        }
      } catch (err) {
        wx.showToast({ title: err.message || '验证失败', icon: 'none' })
      } finally {
        this.setData({ verifying: false, code: '' })
      }
    },

    /** 保存二维码到相册 */
    onSaveQrcode() {
      const url = this.data.account.qrcode
      if (!url) return
      wx.showActionSheet({
        itemList: ['保存二维码到相册'],
        success: () => {
          wx.downloadFile({
            url,
            success: (res) => {
              wx.saveImageToPhotosAlbum({
                filePath: res.tempFilePath,
                success: () => wx.showToast({ title: '已保存到相册' }),
                fail: () => wx.showToast({ title: '保存失败', icon: 'none' }),
              })
            },
          })
        },
      })
    },

    /** 关闭弹窗 */
    onClose() {
      this.triggerEvent('close')
    },

    /** 阻止冒泡 */
    stopPropagation() {},
  },
})
