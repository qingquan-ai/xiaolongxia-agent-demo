from pydantic import BaseModel, Field


class FeishuWebhookPayload(BaseModel):
    event_id: str = Field(..., description="模拟飞书事件 ID")
    sender: str = Field(..., description="模拟消息发送人")
    chat_id: str = Field(..., description="模拟群聊 ID")
    text: str = Field(..., description="模拟消息文本")
