# -*- coding: utf-8 -*-
"""
微信消息处理服务
解析公众号推送的 XML 消息、构建 XML 回复、签名验证
"""
import hashlib
import time
import logging
from xml.etree import ElementTree as ET
from typing import Optional
from dataclasses import dataclass
from config import settings

logger = logging.getLogger(__name__)

# 消息体最大大小（64KB，微信消息通常 < 10KB）
MAX_MESSAGE_BODY_SIZE = 64 * 1024


@dataclass
class WechatMessage:
    """解析后的微信消息"""
    to_user: str = ""
    from_user: str = ""
    create_time: int = 0
    msg_type: str = ""
    content: str = ""
    msg_id: str = ""
    event: str = ""
    event_key: str = ""


def parse_wechat_message(xml_body: bytes) -> WechatMessage:
    """
    解析微信推送的 XML 消息

    消息格式示例：
    <xml>
      <ToUserName><![CDATA[gh_xxx]]></ToUserName>
      <FromUserName><![CDATA[openid_xxx]]></FromUserName>
      <CreateTime>1234567890</CreateTime>
      <MsgType><![CDATA[text]]></MsgType>
      <Content><![CDATA[排版]]></Content>
      <MsgId>1234567890123456</MsgId>
    </xml>
    """
    msg = WechatMessage()
    try:
        root = ET.fromstring(xml_body)
        msg.to_user = _get_xml_text(root, "ToUserName")
        msg.from_user = _get_xml_text(root, "FromUserName")
        msg.create_time = int(_get_xml_text(root, "CreateTime") or "0")
        msg.msg_type = _get_xml_text(root, "MsgType")
        msg.content = _get_xml_text(root, "Content")
        msg.msg_id = _get_xml_text(root, "MsgId")
        msg.event = _get_xml_text(root, "Event")
        msg.event_key = _get_xml_text(root, "EventKey")
    except ET.ParseError as e:
        logger.error(f"XML 解析失败: {e}")
    return msg


def build_text_reply(msg: WechatMessage, reply_content: str) -> str:
    """
    构建文本回复 XML

    NOTE: 回复 XML 中 FromUserName 和 ToUserName 要互换
    """
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{msg.from_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{msg.to_user}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{reply_content}]]></Content>"
        "</xml>"
    )


def verify_wechat_signature(
    signature: str,
    timestamp: str,
    nonce: str,
    token: str,
) -> bool:
    """
    验证微信消息签名

    微信签名算法：
    1. 将 token、timestamp、nonce 三个参数排序
    2. 拼接后 SHA1 加密
    3. 与 signature 对比
    """
    parts = sorted([token, timestamp, nonce])
    hash_str = hashlib.sha1("".join(parts).encode()).hexdigest()
    return hash_str == signature


def get_account_config(account_id: str) -> Optional[dict]:
    """
    根据 account_id 查找对应的公众号配置
    """
    pool = settings.get_account_pool()
    for acc in pool:
        if acc["id"] == account_id:
            return acc
    return None


def _get_xml_text(root: ET.Element, tag: str) -> str:
    """安全地从 XML 元素中获取文本，截断超长内容"""
    element = root.find(tag)
    if element is not None and element.text:
        # 截断超长内容，防止异常数据
        return element.text.strip()[:2000]
    return ""


def validate_message_body(body: bytes) -> bool:
    """
    校验消息体合法性
    防止超大请求消耗服务器资源
    """
    if not body:
        return False
    if len(body) > MAX_MESSAGE_BODY_SIZE:
        return False
    return True
