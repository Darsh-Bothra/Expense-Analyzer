from pydantic import BaseModel, Field


class MerchantStat(BaseModel):
    name: str
    amount: float
    count: int


class CategoryStat(BaseModel):
    name: str
    amount: float
    pct_of_expense: float


class NamedAmount(BaseModel):
    name: str
    amount: float


class NamedCount(BaseModel):
    name: str
    count: int


class FactsPayload(BaseModel):
    income: float
    expense: float
    savings: float
    transaction_count: int
    top_merchants: list[MerchantStat]
    most_frequent_merchant: NamedCount | None = None
    highest_spend_merchant: NamedAmount | None = None
    categories: list[CategoryStat]
    weekend_pct_of_expense: float


class InsightSummary(BaseModel):
    headline: str
    highlights: list[str] = Field(min_length=1, max_length=5)
    watchouts: list[str] = Field(default_factory=list)


class TransactionRow(BaseModel):
    date: str
    merchant: str
    amount: float
    type: str
    category: str


class AnalyzeResponse(BaseModel):
    rows: list[TransactionRow]
    facts: FactsPayload
    insights: InsightSummary
    insights_source: str
    dataset_id: str | None = None


class WorkbookInspect(BaseModel):
    sheets: list[str]
    suggested_sheet: str | None = None
    format: str


class DatasetResponse(BaseModel):
    dataset_id: str
    filename: str
    created_at: str
    rows: list[TransactionRow]
    facts: FactsPayload
    insights: InsightSummary
    insights_source: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ToolCallTrace(BaseModel):
    name: str
    args: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    source: str


class ChatMessageOut(BaseModel):
    role: str
    content: str
    tool_trace: list[ToolCallTrace] | None = None
    created_at: str
