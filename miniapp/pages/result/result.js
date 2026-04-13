/**
 * 排版结果页
 * 调用 AI 排版接口，展示预览结果
 * 支持：主题切换、快捷调整、复制 HTML
 */
const { post, get } = require('../../utils/request')
const { debounce } = require('../../utils/util')

// NOTE: 加载阶段是纯 UI 反馈，与后端实际处理步骤无关
// AI 排版通常耗时 30-120 秒，动画需要覆盖足够长的时间
// 前 8 个阶段每 5 秒切换（共 40 秒），之后在 90% 处循环等待提示
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

// 进度到 90% 后循环展示的等待提示（长文章 AI 响应慢时使用）
const WAITING_HINTS = [
  { text: 'AI 还在努力中...', hint: '文章越长处理越慢，请耐心等待' },
  { text: '正在精雕细琢...', hint: '好的排版需要多一点时间' },
  { text: '快好了，再等等...', hint: 'AI 正在确保排版效果完美' },
  { text: '还在处理中...', hint: '长文章通常需要 1-2 分钟' },
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

  /** 加载进度动画（主阶段 5 秒切换，播完后循环等待提示） */
  _startProgressAnimation() {
    let stageIndex = 0
    // 立即显示第一阶段
    this.setData({
      loadingText: LOADING_STAGES[0].text,
      loadingHint: LOADING_STAGES[0].hint,
      progress: LOADING_STAGES[0].progress,
    })
    stageIndex = 1

    // 主阶段：每 5 秒切换一次（8 个阶段 × 5 秒 = 40 秒覆盖）
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
        // 主阶段播完，切换到等待循环模式
        clearInterval(this._progressTimer)
        this._startWaitingLoop()
      }
    }, 5000)
  },

  /**
   * 等待循环：AI 响应慢时循环展示不同提示
   * 
   * 进度固定在 90%，每 8 秒换一条提示文案，
   * 让用户知道系统没有卡死，只是 AI 处理需要时间。
   */
  _startWaitingLoop() {
    let waitIndex = 0
    this.setData({ progress: 90 })
    this._progressTimer = setInterval(() => {
      const hint = WAITING_HINTS[waitIndex % WAITING_HINTS.length]
      this.setData({
        loadingText: hint.text,
        loadingHint: hint.hint,
      })
      waitIndex++
    }, 8000)
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
    this._scheduleAdjust()
  },

  /** 行高调整 */
  onLineHeightChange(e) {
    this.setData({ lineHeight: e.detail.value })
    this._scheduleAdjust()
  },

  /** 段距调整 */
  onParagraphGapChange(e) {
    this.setData({ paragraphGap: e.detail.value })
    this._scheduleAdjust()
  },

  /**
   * 防抖调度器：200ms 内多次滑动只执行一次 HTML 替换
   * 
   * 不使用 debounce 包装是因为 setTimeout 内部 this 指向不确定，
   * 直接在方法内用箭头函数保持 this 上下文。
   */
  _scheduleAdjust() {
    if (this._adjustTimer) clearTimeout(this._adjustTimer)
    this._adjustTimer = setTimeout(() => {
      this._doApplyAdjustments()
    }, 200)
  },

  /** 应用快捷调整到 HTML（前端本地处理，不重调 AI） */
  _doApplyAdjustments() {
    let html = this.data.fullHtml
    if (!html) return

    const { fontSize, lineHeight, paragraphGap } = this.data
    const actualLineHeight = lineHeight / 10
    // 替换正文字号（不影响标题的字号）
    html = html.replace(/font-size:\s*\d+px/g, `font-size:${fontSize}px`)
    // 替换行高
    html = html.replace(/line-height:\s*[\d.]+/g, `line-height:${actualLineHeight}`)
    // 替换段落间距
    html = html.replace(/margin-bottom:\s*\d+px/g, `margin-bottom:${paragraphGap}px`)
    // NOTE: margin:0 0 16px 格式也需要匹配
    html = html.replace(/margin:\s*0\s+0\s+\d+px/g, `margin:0 0 ${paragraphGap}px`)

    this.setData({ previewHtml: html })
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