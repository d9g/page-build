/**
 * 排版结果页 v4.0
 *
 * 双模式：快速排版（/layout/quick）/ 智能排版（/layout）
 * 主题切换时向后端发请求重新渲染（不再前端替换颜色）
 */
const { post, get } = require('../../utils/request')

// NOTE: 加载阶段仅用于智能排版（AI 耗时长）
const LOADING_STAGES = [
  { text: '正在分析文章结构...', hint: '识别段落、标题、引用', progress: 10 },
  { text: '正在提取关键内容...', hint: '理解文章主题与层次', progress: 20 },
  { text: '正在 AI 智能排版...', hint: '生成专业排版方案', progress: 30 },
  { text: 'AI 正在思考排版策略...', hint: '优化标题与段落配置', progress: 40 },
  { text: '正在优化排版细节...', hint: '调整间距和强调样式', progress: 55 },
  { text: '正在生成样式代码...', hint: '适配微信公众号格式', progress: 65 },
  { text: '正在渲染最终效果...', hint: '转换为微信兼容 HTML', progress: 75 },
  { text: '即将完成...', hint: '正在做最终质量检查', progress: 85 },
]

const WAITING_HINTS = [
  { text: 'AI 还在努力中...', hint: '文章越长处理越慢，请耐心等待' },
  { text: '正在精雕细琢...', hint: '好的排版需要多一点时间' },
  { text: '快好了，再等等...', hint: 'AI 正在确保排版效果完美' },
]

Page({
  data: {
    loading: true,
    loadingText: '正在排版...',
    loadingHint: '',
    progress: 0,
    previewHtml: '',
    fullHtml: '',
    themes: [],
    currentTheme: 'shujuan',
    mode: 'quick',
    fontSize: 16,
    lineHeight: 19,
    letterSpacing: 3,
  },

  onLoad() {
    const app = getApp()
    const mode = app.globalData.layoutMode || 'quick'
    this.setData({ mode })
    this.loadThemes()
    this.doLayout()
  },

  /** 加载主题列表 */
  async loadThemes() {
    try {
      const res = await get('/themes')
      this.setData({ themes: res.themes || [] })
    } catch (err) {
      console.error('加载主题失败', err)
    }
  },

  /** 执行排版 — 根据模式选择不同接口 */
  async doLayout() {
    const app = getApp()
    const content = app.globalData.layoutContent
    if (!content) {
      wx.showToast({ title: '没有待排版的内容', icon: 'none' })
      wx.navigateBack()
      return
    }

    const { mode, currentTheme } = this.data
    this.setData({ loading: true, progress: 0 })

    // NOTE: 智能排版才显示进度动画（快速排版毫秒级完成）
    if (mode === 'ai') {
      this._startProgressAnimation()
      this.setData({ loadingText: '正在分析文章结构...' })
    } else {
      this.setData({ loadingText: '正在渲染排版...', progress: 50 })
    }

    try {
      const endpoint = mode === 'ai' ? '/layout' : '/layout/quick'
      const result = await post(endpoint, {
        content,
        options: { theme: currentTheme },
      })

      this._stopProgressAnimation()
      this.setData({
        loading: false,
        progress: 100,
        previewHtml: result.html || '',
        fullHtml: result.html || '',
      })

      this._layoutContent = content
    } catch (err) {
      this._stopProgressAnimation()
      this.setData({ loading: false })
      wx.showModal({
        title: '排版失败',
        content: err.message || '请稍后再试',
        confirmText: '重试',
        success: (res) => {
          if (res.confirm) this.doLayout()
          else wx.navigateBack()
        },
      })
    }
  },

  /**
   * 切换主题 — 向后端重新请求渲染
   *
   * v4.0 不再前端做颜色替换，而是用新主题重新渲染 Markdown，
   * 确保预设样式（标题/引用/列表等）完全切换。
   */
  async onThemeChange(e) {
    const themeId = e.currentTarget.dataset.id
    if (themeId === this.data.currentTheme) return

    this.setData({ currentTheme: themeId })

    const app = getApp()
    const content = app.globalData.layoutContent
    if (!content) return

    // 使用快速排版接口重新渲染（不管原始模式是什么，切主题只需本地渲染）
    wx.showLoading({ title: '切换主题...' })
    try {
      const result = await post('/layout/quick', {
        content: this._layoutContent || content,
        options: { theme: themeId },
      })
      this.setData({
        previewHtml: result.html || '',
        fullHtml: result.html || '',
      })
    } catch (err) {
      wx.showToast({ title: '切换失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  /** 字号调整 */
  onFontSizeChange(e) {
    this.setData({ fontSize: e.detail.value })
    this._scheduleQuickRerender()
  },

  /** 行高调整 */
  onLineHeightChange(e) {
    this.setData({ lineHeight: e.detail.value })
    this._scheduleQuickRerender()
  },

  /** 字间距调整 */
  onLetterSpacingChange(e) {
    this.setData({ letterSpacing: e.detail.value })
    this._scheduleQuickRerender()
  },

  /**
   * 防抖重渲染：滑块调整后重新调后端渲染
   *
   * 将 fontSize/lineHeight/letterSpacing 的调整值
   * 通过 options 传给后端，后端用调整后的参数重新渲染。
   */
  _scheduleQuickRerender() {
    if (this._adjustTimer) clearTimeout(this._adjustTimer)
    this._adjustTimer = setTimeout(async () => {
      const app = getApp()
      const content = this._layoutContent || app.globalData.layoutContent
      if (!content) return

      const { currentTheme, fontSize, lineHeight, letterSpacing } = this.data

      try {
        const result = await post('/layout/quick', {
          content,
          options: {
            theme: currentTheme,
            fontSize,
            lineHeight: lineHeight / 10,
            letterSpacing: letterSpacing / 10,
          },
        })
        this.setData({
          previewHtml: result.html || '',
          fullHtml: result.html || '',
        })
      } catch (err) {
        console.error('调整渲染失败', err)
      }
    }, 500)
  },

  /** 复制 HTML */
  onCopyHtml() {
    const html = this.data.fullHtml
    if (!html) {
      wx.showToast({ title: '没有可复制的内容', icon: 'none' })
      return
    }
    wx.setClipboardData({
      data: html,
      success: () => {
        wx.showToast({ title: '已复制，去公众号粘贴', icon: 'success' })
      },
    })
  },

  /** 重新排版 */
  onRetry() {
    this.setData({
      previewHtml: '',
      fullHtml: '',
      fontSize: 16,
      lineHeight: 19,
      letterSpacing: 3,
    })
    this.doLayout()
  },

  // ===== 进度动画（仅智能排版使用） =====
  _startProgressAnimation() {
    let stageIndex = 0
    this.setData({
      loadingText: LOADING_STAGES[0].text,
      loadingHint: LOADING_STAGES[0].hint,
      progress: LOADING_STAGES[0].progress,
    })
    stageIndex = 1

    this._progressTimer = setInterval(() => {
      if (stageIndex < LOADING_STAGES.length) {
        const stage = LOADING_STAGES[stageIndex]
        this.setData({
          loadingText: stage.text,
          loadingHint: stage.hint,
          progress: stage.progress,
        })
        stageIndex++
      } else {
        clearInterval(this._progressTimer)
        this._startWaitingLoop()
      }
    }, 5000)
  },

  _startWaitingLoop() {
    let waitIndex = 0
    this.setData({ progress: 90 })
    this._progressTimer = setInterval(() => {
      const hint = WAITING_HINTS[waitIndex % WAITING_HINTS.length]
      this.setData({ loadingText: hint.text, loadingHint: hint.hint })
      waitIndex++
    }, 8000)
  },

  _stopProgressAnimation() {
    if (this._progressTimer) {
      clearInterval(this._progressTimer)
      this._progressTimer = null
    }
  },

  onShareAppMessage() {
    return {
      title: '公众号排版工具 — 一键美化文章格式',
      path: '/pages/index/index',
    }
  },
})