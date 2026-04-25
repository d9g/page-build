/**
 * 首页逻辑 v4.0
 *
 * 双模式入口：快速排版（本地）/ 智能排版（AI）
 */
const { post, get } = require('../../utils/request')
const { ensureLogin } = require('../../utils/auth')
const { saveDraft, loadDraft, clearDraft } = require('../../utils/storage')
const { debounce } = require('../../utils/util')

const autoSaveDraft = debounce(function (content) {
  saveDraft(content)
}, 1000)

Page({
  data: {
    content: '',
    contentLength: 0,
    canSubmit: false,
    submitting: false,
    submitMode: '',
    hintText: '',
    showDraftTip: false,
    showVerifyModal: false,
  },

  onLoad() {
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
    autoSaveDraft(content)
  },

  /** 粘贴 */
  onPaste() {
    wx.getClipboardData({
      success: (res) => {
        if (res.data) {
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

  /**
   * 快速排版 — 需验证关注公众号
   *
   * 不调 AI，直接将内容当 Markdown 渲染
   */
  async onQuickSubmit() {
    if (!this.data.canSubmit || this.data.submitting) return
    this.setData({ submitting: true, submitMode: 'quick' })

    try {
      await ensureLogin()
      const app = getApp()

      // NOTE: 快速排版也需要验证关注公众号
      if (!app.globalData.verified) {
        const status = await get('/user/status')
        if (!status.verified) {
          this.setData({ showVerifyModal: true, submitting: false })
          this._pendingMode = 'quick'
          return
        }
        app.globalData.verified = true
      }

      clearDraft()
      app.globalData.layoutContent = this.data.content
      app.globalData.layoutMode = 'quick'
      wx.navigateTo({ url: '/pages/result/result' })
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    } finally {
      setTimeout(() => this.setData({ submitting: false, submitMode: '' }), 1000)
    }
  },

  /**
   * 智能排版 — 需验证码
   *
   * AI 自动识别文本结构 → 转 Markdown → 渲染
   */
  async onAiSubmit() {
    if (!this.data.canSubmit || this.data.submitting) return
    this.setData({ submitting: true, submitMode: 'ai' })

    try {
      await ensureLogin()
      const app = getApp()

      if (!app.globalData.verified) {
        const status = await get('/user/status')
        if (!status.verified) {
          this.setData({ showVerifyModal: true, submitting: false })
          this._pendingMode = 'ai'
          return
        }
        app.globalData.verified = true
      }

      clearDraft()
      app.globalData.layoutContent = this.data.content
      app.globalData.layoutMode = 'ai'
      wx.navigateTo({ url: '/pages/result/result' })
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    } finally {
      setTimeout(() => this.setData({ submitting: false, submitMode: '' }), 1000)
    }
  },

  /** 验证弹窗关闭 */
  onVerifyClose() {
    this.setData({ showVerifyModal: false })
  },

  /** 验证通过 — 自动触发之前挂起的排版模式 */
  onVerified() {
    this.setData({ showVerifyModal: false })
    getApp().globalData.verified = true
    wx.showToast({ title: '验证成功！', icon: 'success' })

    const mode = this._pendingMode || 'quick'
    setTimeout(() => {
      if (mode === 'ai') {
        this.onAiSubmit()
      } else {
        this.onQuickSubmit()
      }
    }, 500)
  },

  /** 分享 */
  onShareAppMessage() {
    return {
      title: '公众号排版工具 — 快速排版 & AI 智能排版',
      path: '/pages/index/index',
    }
  },
})
