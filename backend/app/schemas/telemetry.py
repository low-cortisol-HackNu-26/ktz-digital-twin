# Pydantic v2 schemas for API serialization of telemetry data.
# (Separate from ORM models — thin conversion layer.)
#
# class TelemetryPacketSchema(BaseModel):
#   All fields matching TelemetryRecord columns, camelCase aliases for frontend JSON
#   model_config: populate_by_name=True, from_attributes=True
#
# class HealthIndexSchema(BaseModel):
#   score: float (0–100)
#   grade: Literal["A","B","C","D","E"]
#   category: Literal["NORMAL","WARNING","CRITICAL"]
#   factors: list[HealthFactorSchema]
#   timestamp: datetime
#
# class HealthFactorSchema(BaseModel):
#   parameter: str
#   value: float
#   contribution: float
#   label: str
#
# class TelemetryPacketWithHealthSchema(TelemetryPacketSchema):
#   healthIndex: HealthIndexSchema  ← combined response for WS and /latest endpoint
