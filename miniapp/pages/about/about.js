Page({
  onFeedback() {
    // 跳转客服会话或留言
    wx.showModal({
      title: '意见反馈',
      content: '如有问题或建议，请关注公众号后发送「反馈」',
      showCancel: false,
    })
  },
})
