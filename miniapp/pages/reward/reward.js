/**
 * 激励视频页
 * 观看广告解锁高级主题（需开通流量主后替换广告单元 ID）
 */
Page({
  data: { themeId: '' },

  onLoad(options) {
    this.data.themeId = options.themeId || 'dark'
    this.setData({ themeId: this.data.themeId })
  },

  onWatchAd() {
    // NOTE: 需要开通流量主后替换为真实广告单元 ID
    if (!wx.createRewardedVideoAd) {
      wx.showToast({ title: '当前版本不支持', icon: 'none' })
      return
    }

    const ad = wx.createRewardedVideoAd({ adUnitId: 'adunit-placeholder' })
    ad.onClose((res) => {
      if (res && res.isEnded) {
        wx.setStorageSync(`theme_unlocked_${this.data.themeId}`, Date.now())
        wx.showToast({ title: '解锁成功！' })
        setTimeout(() => wx.navigateBack(), 500)
      } else {
        wx.showToast({ title: '需要看完视频才能解锁哦', icon: 'none' })
      }
    })
    ad.show().catch(() => {
      wx.showToast({ title: '广告加载失败，请稍后再试', icon: 'none' })
    })
  },
})
