# pragma: no cover
from typing import Literal, TypedDict


class ExternalIds(TypedDict, total=False):
    """MPT API External Ids API representation."""
    reference: str
    invoice: str
    vendor: str


class SearchCriteria(TypedDict):
    """MPT API Charge search criteria."""
    criteria: str
    value: str


class Search(TypedDict, total=False):
    """MPT API Search."""
    subscription: SearchCriteria
    order: SearchCriteria
    item: SearchCriteria


class Period(TypedDict):
    """MPT API Journal period."""
    start: str
    end: str


class Currency(TypedDict):
    """MPT API Journal currency."""
    purchase: str
    sale: str
    rate: float


class Price(TypedDict, total=False):
    """MPT API Journal Price."""
    currency: Currency
    markup: float
    markupSource: str
    margin: float
    unitPP: float
    PPx1: float
    unitSP: float
    SPx1: float


class Description(TypedDict, total=False):
    """MPT API Journal descriptions."""
    value1: str
    value2: str


class JournalRef(TypedDict):
    """MPT API Journal reference representation."""
    id: str
    name: str
    dueDate: str


class LedgerRef(TypedDict):
    """MPT API Ledger reference representation."""
    id: str


class CustomLedgerRef(TypedDict):
    """MPT API Custom Ledger reference representation."""
    id: str
    name: str


class ParentRef(TypedDict):
    """MPT API parent Charge reference representation."""
    id: str
    externalIds: ExternalIds


class LicenseeRef(TypedDict):
    """MPT API Licensee reference representation."""
    id: str
    icon: str
    name: str
    externalId: str


class AgreementRef(TypedDict):
    """MPT API Agreement reference representation."""
    id: str
    icon: str
    status: str
    name: str


class SubscriptionRef(TypedDict):
    """MPT API Subscription reference representation."""
    id: str
    name: str


class OrderRef(TypedDict):
    """MPT API Order reference representation."""
    id: str


class ItemExternalIds(TypedDict):
    """MPT API Item external ids."""
    vendor: str
    operations: str


class ItemRef(TypedDict):
    """MPT API Item reference representation."""
    id: str
    name: str
    externalIds: ItemExternalIds


class AuthorizationRef(TypedDict):
    """MPT API Authorization reference representation."""
    id: str
    name: str
    currency: str


class StatementRef(TypedDict):
    """MPT API Statement reference representation."""
    id: str


class JournalChargesQuantity(TypedDict):
    """MPT API Charge quantity reference representation."""
    total: int
    split: int
    ready: int
    error: int
    skipped: int


class PersonRef(TypedDict):
    """MPT API Audit person reference representation."""
    id: str
    name: str
    icon: str


class AuditEntry(TypedDict):
    """MPT API audit entry."""
    at: str
    by: PersonRef


class AuditLog(TypedDict):
    """MPT API audit object representation."""
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


class JournalExternalIds(TypedDict):
    """MPT API Journal external Ids."""
    operations: str
    vendor: str


class VendorRef(TypedDict):
    """MPT API Vendor reference representation."""
    id: str
    icon: str
    type: Literal["Client"]  # TODO: vendor ref with client type???
    status: Literal["Active"]  # TODO: only active status???
    name: str


class SellerRef(TypedDict):
    """MPT API Seller reference representation."""
    id: str
    icon: str
    externalId: str
    name: str


class BuyerRef(TypedDict):
    """MPT API Buyer reference representation."""
    id: str
    icon: str
    name: str


class ErpData(TypedDict, total=False):
    """MPT API ERP data representation."""
    erpCountryCode: str
    defaultErpProductId: str
    defaultErpProductName: str
    cdg: str
    scu: str
    cco: str
    erpItemId: str


class OwnerRef(TypedDict):
    """MPT API Owner reference representation."""
    id: str
    icon: str
    externalId: str
    name: str


class ProductExternalIds(TypedDict):
    """MPT API Product external ids."""
    operations: str
    defaultErpItem: str


class ProductRef(TypedDict):
    """MPT API Product reference representation."""
    id: str
    name: str
    externalIds: ProductExternalIds
    icon: str
    status: str


class ErrorInfo(TypedDict):
    """MPT API Journal error info."""
    errorCode: str
    errorMessage: str
    id: str
    message: str


class Journal(TypedDict):
    """MPT API journal."""
    id: str
    name: str
    description: str
    externalIds: JournalExternalIds
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
    """MPT API Journal Attachment."""
    id: str
    name: str
    type: str
    contentType: str
    description: str
    filename: str
    audit: AuditLog


class Split(TypedDict):
    """MPT API Split charge."""
    percentage: int


class Attributes(TypedDict, total=False):
    """MPT API Journal Attributed."""
    documentNumber: str
    orderType: str
    externalDocumentNo: str
    externalDocumentNo2: str
    yourReference: str


class ChargeUpload(TypedDict):
    """MPT API Charge upload status."""
    status: str
    errors: list[str]


class JournalCharge(TypedDict, total=False):
    """MPT API Charge."""
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
