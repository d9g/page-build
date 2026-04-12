/**
 * 本地存储封装
 * 草稿自动保存与恢复
 */

const DRAFT_KEY = 'layout_draft'
const DRAFT_TIME_KEY = 'layout_draft_time'

/**
 * 保存草稿
 * @param {string} content 文章内容
 */
function saveDraft(content) {
  if (!content || content.length < 10) return
  wx.setStorageSync(DRAFT_KEY, content)
  wx.setStorageSync(DRAFT_TIME_KEY, Date.now())
}

/**
 * 读取草稿
 * @returns {object|null} {content, savedAt} 或 null
 */
function loadDraft() {
  const content = wx.getStorageSync(DRAFT_KEY)
  const savedAt = wx.getStorageSync(DRAFT_TIME_KEY)
  if (!content) return null
  return { content, savedAt }
}

/**
 * 清除草稿
 */
function clearDraft() {
  wx.removeStorageSync(DRAFT_KEY)
  wx.removeStorageSync(DRAFT_TIME_KEY)
}

module.exports = { saveDraft, loadDraft, clearDraft }
