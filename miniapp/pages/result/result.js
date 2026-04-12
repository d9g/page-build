/**
 * 排版结果页
 * 调用 AI 排版接口，展示预览结果
 * 支持：主题切换、复制 HTML
 */
const { post, get } = require('../../utils/request')
const { debounce } = require('../../utils/util')

// 加载阶段文案
const LOADING_STAGES = [
  { text: '正在分析文章结构...', hint: '识别段落、标题、引用', progress: 15 },
  { text: '正在 AI 智能排版...', hint: '生成专业排版方案', progress: 45 },
  { text: '优化排版细节...', hint: '调整间距和强调样式', progress: 75 },
  { text: '生成 HTML...', hint: '即将完成', progress: 90 },
]

Page({
  data: {
    loading: true,
    loadingText: '正在分析文章结构...',
    loadingHint: '',
    progress: 0,
    previewHtml: '',
    fullHtml: '',
    sections: [],
    themes: [],
    currentTheme: 'default',
  },

  onLoad() {
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

  /** 执行排版 */
  async doLayout() {
    const app = getApp()
    const content = app.globalData.layoutContent
    if (!content) {
      wx.showToast({ title: '没有待排版的内容', icon: 'none' })
      wx.navigateBack()
      return
    }

    this.setData({ loading: true })
    this._startProgressAnimation()

    try {
      const result = await post('/layout', {
        content,
        options: { theme: this.data.currentTheme },
      })

      this._stopProgressAnimation()

      this.setData({
        loading: false,
        progress: 100,
        sections: result.sections || [],
        previewHtml: result.html || '',
        fullHtml: result.html || '',
      })

      this._layoutContent = content
      this._promptVersion = result.prompt_version
    } catch (err) {
      this._stopProgressAnimation()
      this.setData({ loading: false })
      wx.showModal({
        title: '排版失败',
        content: err.message || '请稍后再试',
        confirmText: '重试',
        success: (res) => {
          if (res.confirm) {
            this.doLayout()
          } else {
            wx.navigateBack()
          }
        },
      })
    }
  },

  /** 模拟加载进度动画 */
  _startProgressAnimation() {
    let stageIndex = 0
    this._progressTimer = setInterval(() => {
      if (stageIndex < LOADING_STAGES.length) {
        const stage = LOADING_STAGES[stageIndex]
        this.setData({
          loadingText: stage.text,
          loadingHint: stage.hint,
          progress: stage.progress,
        })
        stageIndex++
      }
    }, 5000)
  },

  _stopProgressAnimation() {
    if (this._progressTimer) {
      clearInterval(this._progressTimer)
      this._progressTimer = null
    }
  },

  /** 切换主题（本地切换） */
  onThemeChange: debounce(function (e) {
    const themeId = e.currentTarget.dataset.id
    if (themeId === this.data.currentTheme) return

    const theme = this.data.themes.find(t => t.id === themeId)
    if (theme && theme.is_premium) {
      const unlocked = wx.getStorageSync(`theme_unlocked_${themeId}`)
      if (!unlocked) {
        wx.showModal({
          title: '高级主题',
          content: '观看一段短视频即可免费使用该主题',
          confirmText: '去解锁',
          success: (res) => {
            if (res.confirm) {
              wx.navigateTo({ url: `/pages/reward/reward?themeId=${themeId}` })
            }
          },
        })
        return
      }
    }

    this.setData({ currentTheme: themeId })
    const themeStyles = theme?.styles || {}
    const newHtml = this.applyThemeToHtml(this.data.fullHtml, themeStyles)
    this.setData({ previewHtml: newHtml })
  }, 300),

  /** 应用主题样式到 HTML */
  applyThemeToHtml(html, styles) {
    if (!html || !styles) return html
    const defaultColors = {
      title_color: '#333333',
      body_color: '#3f3f3f',
      accent_color: '#07C160',
      quote_border_color: '#07C160',
    }
    let result = html
    for (const [key, color] of Object.entries(defaultColors)) {
      const newColor = styles[key] || color
      result = result.replace(new RegExp(color, 'g'), newColor)
    }
    return result
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
        wx.showToast({ title: '已复制到剪贴板', icon: 'success' })
      },
    })
  },

  /** 返回首页 */
  onGoBack() {
    wx.navigateBack()
  },
})