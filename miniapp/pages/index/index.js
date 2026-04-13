/**
 * 首页逻辑
 * 输入文章内容 → 校验 → 跳转排版结果页
 */
const { post, get } = require('../../utils/request')
const { ensureLogin } = require('../../utils/auth')
const { saveDraft, loadDraft, clearDraft } = require('../../utils/storage')
const { debounce } = require('../../utils/util')

// 草稿自动保存（防抖 1 秒）
const autoSaveDraft = debounce(function (content) {
  saveDraft(content)
}, 1000)

Page({
  data: {
    content: '',
    contentLength: 0,
    canSubmit: false,
    submitting: false,
    hintText: '',
    showDraftTip: false,
    showVerifyModal: false,
  },

  onLoad() {
    // 检查草稿
    const draft = loadDraft()
    if (draft && draft.content) {
      this.setData({ showDraftTip: true })
      this._draftContent = draft.content
    }
  },

  /** 输入事件 */
  onInput(e) {
    const content = e.detail.value
    const len = content.length

    let hintText = ''
    let canSubmit = false
    if (len > 0 && len < 50) {
      hintText = '内容过短，建议至少 50 字'
    } else if (len >= 50) {
      canSubmit = true
    }

    this.setData({ content, contentLength: len, canSubmit, hintText })

    // 自动保存草稿
    autoSaveDraft(content)
  },

  /** 粘贴（替换当前内容，而非追加） */
  onPaste() {
    wx.getClipboardData({
      success: (res) => {
        if (res.data) {
          // 清理 HTML 标签
          const clean = res.data.replace(/<[^>]+>/g, '')
          const trimmed = clean.slice(0, 3000)
          this.setData({
            content: trimmed,
            contentLength: trimmed.length,
            canSubmit: trimmed.length >= 50,
            hintText: trimmed.length < 50 ? '内容过短，建议至少 50 字' : '',
          })
          saveDraft(trimmed)
        }
      },
    })
  },

  /** 清空 */
  onClear() {
    if (!this.data.content) return
    wx.showModal({
      title: '确认清空',
      content: '确定要清空所有内容吗？',
      success: (res) => {
        if (res.confirm) {
          this.setData({ content: '', contentLength: 0, canSubmit: false, hintText: '' })
          clearDraft()
        }
      },
    })
  },

  /** 恢复草稿 */
  onRestoreDraft() {
    if (this._draftContent) {
      const content = this._draftContent
      this.setData({
        content,
        contentLength: content.length,
        canSubmit: content.length >= 50,
        showDraftTip: false,
        hintText: '',
      })
    }
  },

  /** 忽略草稿 */
  onDismissDraft() {
    this.setData({ showDraftTip: false })
    clearDraft()
  },

  /** 提交排版 */
  async onSubmit() {
    if (!this.data.canSubmit || this.data.submitting) return

    this.setData({ submitting: true })

    try {
      await ensureLogin()

      // 检查验证状态
      const app = getApp()
      if (!app.globalData.verified) {
        const status = await get('/user/status')
        if (!status.verified) {
          this.setData({ showVerifyModal: true, submitting: false })
          return
        }
        app.globalData.verified = true
      }

      // 清除草稿并跳转结果页
      clearDraft()
      // 将内容存到全局，结果页读取
      app.globalData.layoutContent = this.data.content
      wx.navigateTo({ url: '/pages/result/result' })
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    } finally {
      // NOTE: 延迟重置，避免页面返回后立即可再次点击
      setTimeout(() => this.setData({ submitting: false }), 1000)
    }
  },

  /** 验证弹窗关闭 */
  onVerifyClose() {
    this.setData({ showVerifyModal: false })
  },

  /** 验证通过 */
  onVerified() {
    this.setData({ showVerifyModal: false })
    getApp().globalData.verified = true
    wx.showToast({ title: '验证成功！', icon: 'success' })
    // 自动触发排版
    setTimeout(() => this.onSubmit(), 500)
  },

  /** 分享配置 */
  onShareAppMessage() {
    return {
      title: 'AI 智能排版 — 公众号文章一键美化',
      path: '/pages/index/index',
    }
  },
})
