# Pydantic v2 schemas for alert API responses.
#
# class AlertSchema(BaseModel):
#   id: UUID
#   locomotiveId: str
#   code: str
#   severity: Literal["info","warning","critical"]
#   message: str
#   firedAt: datetime
#   resolvedAt: datetime | None
#   acknowledgedAt: datetime | None
#   acknowledgedBy: str | None
#   model_config: from_attributes=True
#
# class AcknowledgeRequest(BaseModel):
#   (empty body — actor determined from JWT)
