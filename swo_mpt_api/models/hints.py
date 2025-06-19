# pragma: no cover
from typing import Literal, TypedDict


class ExternalIds(TypedDict, total=False):
    reference: str
    invoice: str
    vendor: str


class SearchCriteria(TypedDict):
    criteria: str
    value: str


class Search(TypedDict, total=False):
    subscription: SearchCriteria
    order: SearchCriteria
    item: SearchCriteria


class Period(TypedDict):
    start: str
    end: str


class Currency(TypedDict):
    purchase: str
    sale: str
    rate: float


class Price(TypedDict, total=False):
    currency: Currency
    markup: float
    markupSource: str
    margin: float
    unitPP: float
    PPx1: float
    unitSP: float
    SPx1: float


class Description(TypedDict, total=False):
    value1: str
    value2: str


class JournalRef(TypedDict):
    id: str
    name: str
    dueDate: str


class LedgerRef(TypedDict):
    id: str


class CustomLedgerRef(TypedDict):
    id: str
    name: str


class ParentRef(TypedDict):
    id: str
    externalIds: ExternalIds


class LicenseeRef(TypedDict):
    id: str
    icon: str
    name: str
    externalId: str


class AgreementRef(TypedDict):
    id: str
    icon: str
    status: str
    name: str


class SubscriptionRef(TypedDict):
    id: str
    name: str


class OrderRef(TypedDict):
    id: str


class ItemExternalIds(TypedDict):
    vendor: str
    operations: str


class ItemRef(TypedDict):
    id: str
    name: str
    externalIds: ItemExternalIds


class AuthorizationRef(TypedDict):
    id: str
    name: str
    currency: str


class StatementRef(TypedDict):
    id: str


class JournalChargesQuantity(TypedDict):
    total: int
    split: int
    ready: int
    error: int
    skipped: int


class PersonRef(TypedDict):
    id: str
    name: str
    icon: str


class AuditEntry(TypedDict):
    at: str
    by: PersonRef


class AuditLog(TypedDict):
    created: AuditEntry
    updated: AuditEntry
    draft: AuditEntry
    deleted: AuditEntry
    error: AuditEntry
    validating: AuditEntry
    validated: AuditEntry
    review: AuditEntry
    enquiring: AuditEntry
    generating: AuditEntry
    generated: AuditEntry
    accepted: AuditEntry
    completed: AuditEntry


class ExternalIds(TypedDict):
    operations: str
    vendor: str


class VendorRef(TypedDict):
    id: str
    icon: str
    type: Literal["Client"]
    status: Literal["Active"]
    name: str


class SellerRef(TypedDict):
    id: str
    icon: str
    externalId: str
    name: str


class BuyerRef(TypedDict):
    id: str
    icon: str
    name: str


class ErpData(TypedDict, total=False):
    erpCountryCode: str
    defaultErpProductId: str
    defaultErpProductName: str
    cdg: str
    scu: str
    cco: str
    erpItemId: str


class OwnerRef(TypedDict):
    id: str
    icon: str
    externalId: str
    name: str


class ProductExternalIds(TypedDict):
    operations: str
    defaultErpItem: str


class ProductRef(TypedDict):
    id: str
    name: str
    externalIds: ProductExternalIds
    icon: str
    status: str


class Currency(TypedDict):
    purchase: str
    sale: str
    rate: float


class ErrorInfo(TypedDict):
    errorCode: str
    errorMessage: str
    id: str
    message: str


class Journal(TypedDict):
    id: str
    name: str
    description: str
    externalIds: ExternalIds
    notes: str
    status: str
    vendor: VendorRef
    owner: OwnerRef
    product: ProductRef
    authorization: AuthorizationRef
    dueDate: str
    assignee: PersonRef
    price: Price
    upload: JournalChargesQuantity
    processing: JournalChargesQuantity
    error: ErrorInfo
    audit: AuditLog


class JournalAttachment(TypedDict):
    id: str
    name: str
    type: str
    contentType: str
    description: str
    filename: str
    audit: AuditLog


class Split(TypedDict):
    percentage: int


class Attributes(TypedDict, total=False):
    documentNumber: str
    orderType: str
    externalDocumentNo: str
    externalDocumentNo2: str
    yourReference: str


class ChargeUpload(TypedDict):
    status: str
    errors: list[str]


class JournalCharge(TypedDict, total=False):
    id: str
    externalIds: ExternalIds
    search: Search
    period: Period
    quantity: float
    price: Price
    segment: str
    description: Description
    journal: JournalRef
    ledger: LedgerRef
    customLedger: CustomLedgerRef
    parent: ParentRef
    billingType: str
    upload: ChargeUpload
    licensee: LicenseeRef
    agreement: AgreementRef
    subscription: SubscriptionRef
    order: OrderRef
    item: ItemRef
    authorization: AuthorizationRef
    statement: StatementRef
    statementType: str
    processing: JournalChargesQuantity
    erpData: ErpData
    buyer: BuyerRef
    vendor: VendorRef
    seller: SellerRef
    attributes: Attributes
    split: Split
