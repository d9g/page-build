/**
 * 通用工具函数
 */

/**
 * 防抖函数
 * 延迟执行，期间如果再次调用则重新计时
 * @param {Function} fn 要执行的函数
 * @param {number} delay 延迟毫秒数
 * @returns {Function} 包装后的防抖函数
 */
function debounce(fn, delay = 200) {
  let timer = null
  return function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      fn.apply(this, args)
      timer = null
    }, delay)
  }
}

/**
 * 格式化时间
 * @param {number} timestamp 时间戳
 * @returns {string} 格式化字符串
 */
function formatTime(timestamp) {
  const date = new Date(timestamp)
  const pad = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

module.exports = { debounce, formatTime }
