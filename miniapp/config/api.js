/**
 * API 地址配置
 * 开发环境和生产环境使用不同的 API 地址
 */
const ENV = {
  // 开发环境 — 使用本地后端
  dev: {
    baseUrl: 'http://localhost:8000',
  },
  // 生产环境 — 使用正式域名（在 .env 中配置）
  prod: {
    baseUrl: 'https://pb.d9g.com.cn',
  },
}

// NOTE: 切换环境时修改此值，或通过微信开发者工具的编译模式控制
const currentEnv = 'prod'

module.exports = {
  baseUrl: ENV[currentEnv].baseUrl,
  apiPrefix: '/api/v1',
}
