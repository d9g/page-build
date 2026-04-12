/**
 * 排版结果页
 * 调用 AI 排版接口，展示预览结果
 * 支持：主题切换、字号/行高/段距 Slider 调整、复制 HTML
 */
const { post, get } = require('../../utils/request')
const { debounce } = require('../../utils/util')

// 加载阶段文案，模拟进度反馈
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
    // Slider 默认值
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

    this.setData({ loading: true })

    // 启动模拟进度动画，给用户视觉反馈
    this._startProgressAnimation()

    try {
      const result = await post('/layout', {
        content,
        options: { theme: this.data.currentTheme },
      })

      // 停止进度动画
      this._stopProgressAnimation()

      this.setData({
        loading: false,
        progress: 100,
        sections: result.sections || [],
        previewHtml: result.html || '',
        fullHtml: result.html || '',
      })

      // 保存结果供重新排版使用
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
    }, 1500)
    // 立即显示第一阶段
    if (LOADING_STAGES.length > 0) {
      this.setData({
        loadingText: LOADING_STAGES[0].text,
        loadingHint: LOADING_STAGES[0].hint,
        progress: LOADING_STAGES[0].progress,
      })
    }
  },

  _stopProgressAnimation() {
    if (this._progressTimer) {
      clearInterval(this._progressTimer)
      this._progressTimer = null
    }
  },

  /** 字号调整（前端本地，不调后端） */
  onFontSizeChange(e) {
    this.setData({ fontSize: e.detail.value })
  },

  /** 行高调整（前端本地） */
  onLineHeightChange(e) {
    this.setData({ lineHeight: e.detail.value })
  },

  /** 段距调整（前端本地） */
  onParagraphGapChange(e) {
    this.setData({ paragraphGap: e.detail.value })
  },

  /** 切换主题 */
  onThemeChange: debounce(function (e) {
    const themeId = e.currentTarget.dataset.id
    if (themeId === this.data.currentTheme) return

    // 检查是否是付费主题，需要先解锁
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

    // 重新请求排版（应用新主题）
    if (this._layoutContent) {
      this.setData({ loading: true, loadingText: '正在切换主题...', progress: 50 })
      post('/layout', {
        content: this._layoutContent,
        options: { theme: themeId },
      }).then(result => {
        this.setData({
          loading: false,
          previewHtml: result.html || '',
          fullHtml: result.html || '',
        })
      }).catch(() => {
        this.setData({ loading: false })
        wx.showToast({ title: '主题切换失败', icon: 'none' })
      })
    }
  }, 300),

  /** 复制 HTML */
  onCopyHtml() {
    if (!this.data.fullHtml) {
      wx.showToast({ title: '没有可复制的内容', icon: 'none' })
      return
    }
    wx.setClipboardData({
      data: this.data.fullHtml,
      success: () => {
        wx.showToast({ title: '已复制，去公众号粘贴吧' })
      },
    })
  },

  /** 重新排版 */
  onRetry() {
    wx.navigateBack()
  },

  onUnload() {
    this._stopProgressAnimation()
  },
})
