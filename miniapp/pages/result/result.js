/**
 * 排版结果页
 * 调用 AI 排版接口，展示预览结果
 * 支持：主题切换、快捷调整、复制 HTML
 */
const { post, get } = require('../../utils/request')

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

  /**
   * 切换主题（纯本地操作，不调用 AI）
   * 
   * 去掉了 debounce：主题切换是单次点击事件不是连续滑动，
   * 防抖只会徒增 300ms 延迟，让用户觉得卡顿。
   */
  onThemeChange(e) {
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

    const themeStyles = theme?.styles || {}
    const newHtml = this.applyThemeToHtml(this.data.fullHtml, themeStyles)
    // NOTE: 合并为一次 setData 减少跨线程通信
    this.setData({ currentTheme: themeId, previewHtml: newHtml })
  },

  /**
   * 应用主题样式到 HTML（颜色替换）
   * 
   * 用一次正则匹配所有颜色值并替换，比 4 次全文遍历快得多。
   * 始终基于 fullHtml（AI 原始输出）做替换，保证主题可反复切换。
   */
  applyThemeToHtml(html, styles) {
    if (!html || !styles) return html

    // 默认颜色 → 主题颜色映射表
    const colorMap = {
      '#333333': styles.title_color || '#333333',
      '#3f3f3f': styles.body_color || '#3f3f3f',
      '#07c160': styles.accent_color || '#07C160',
    }

    // 单次正则替换所有匹配的颜色值（不区分大小写）
    const colorPattern = /#333333|#3f3f3f|#07c160/gi
    return html.replace(colorPattern, (match) => {
      return colorMap[match.toLowerCase()] || match
    })
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