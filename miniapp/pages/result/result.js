/**
 * 排版结果页
 * 调用 AI 排版接口，展示预览结果
 * 支持：主题切换、快捷调整、复制 HTML
 */
const { post, get } = require('../../utils/request')
const { debounce } = require('../../utils/util')

// 加载阶段文案（每 2 秒切换一次，给用户持续反馈）
const LOADING_STAGES = [
  { text: '正在分析文章结构...', hint: '识别段落、标题、引用', progress: 15 },
  { text: '正在 AI 智能排版...', hint: '生成专业排版方案', progress: 35 },
  { text: 'AI 正在思考排版策略...', hint: '优化标题与段落配置', progress: 50 },
  { text: '优化排版细节...', hint: '调整间距和强调样式', progress: 65 },
  { text: '生成微信兼容 HTML...', hint: '即将完成', progress: 80 },
  { text: '最终检查...', hint: '确保排版效果完美', progress: 90 },
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
    // 快捷调整参数（lineHeight 为整数 14-26，实际应用时除以10）
    fontSize: 15,
    lineHeight: 18,
    paragraphGap: 16,
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

    this.setData({ loading: true, progress: 0 })
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

      // 缓存排版内容，用于重排
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

  /** 加载进度动画（2 秒切换阶段，给用户持续反馈感） */
  _startProgressAnimation() {
    let stageIndex = 0
    // 立即显示第一阶段
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
      }
    }, 2000)
  },

  _stopProgressAnimation() {
    if (this._progressTimer) {
      clearInterval(this._progressTimer)
      this._progressTimer = null
    }
  },

  /** 切换主题（本地切换，不调用 AI） */
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

  /** 应用主题样式到 HTML（颜色替换） */
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

  /** 字号调整 */
  onFontSizeChange(e) {
    this.setData({ fontSize: e.detail.value })
    this._applyAdjustments()
  },

  /** 行高调整 */
  onLineHeightChange(e) {
    this.setData({ lineHeight: e.detail.value })
    this._applyAdjustments()
  },

  /** 段距调整 */
  onParagraphGapChange(e) {
    this.setData({ paragraphGap: e.detail.value })
    this._applyAdjustments()
  },

  /** 应用快捷调整到 HTML（前端本地处理，不重调 AI） */
  _applyAdjustments: debounce(function () {
    let html = this.data.fullHtml
    if (!html) return

    const { fontSize, lineHeight, paragraphGap } = this.data
    const actualLineHeight = lineHeight / 10
    // 替换字号
    html = html.replace(/font-size:\s*\d+px/g, `font-size:${fontSize}px`)
    // 替换行高
    html = html.replace(/line-height:\s*[\d.]+/g, `line-height:${actualLineHeight}`)
    // 替换段落间距
    html = html.replace(/margin-bottom:\s*\d+px/g, `margin-bottom:${paragraphGap}px`)

    this.setData({ previewHtml: html })
  }, 200),

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

  /** 重新排版 */
  onRetry() {
    this.setData({
      previewHtml: '',
      fullHtml: '',
      sections: [],
      fontSize: 15,
      lineHeight: 18,
      paragraphGap: 16,
    })
    this.doLayout()
  },

  /** 返回首页 */
  onGoBack() {
    wx.navigateBack()
  },

  /** 分享配置 */
  onShareAppMessage() {
    return {
      title: '公众号文章一键 AI 排版，效果超赞！',
      path: '/pages/index/index',
    }
  },
})