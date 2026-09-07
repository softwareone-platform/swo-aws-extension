from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self


class FinOpsFields(StrEnum):
    """Fields in the FinOps Airtable table."""

    ACCOUNT_ID = "Account ID"
    BUYER_ID = "Buyer ID"
    AGREEMENT_ID = "Agreement ID"
    STATUS = "Status"
    ENTITLEMENT_ID = "Entitlement ID"
    CREATED = "Created"
    LAST_USAGE_DATE = "Last Usage Date"


@dataclass
class FinOpsRecord:
    """Represent the FinOps record from Airtable."""

    account_id: str
    buyer_id: str
    agreement_id: str
    entitlement_id: str
    status: str
    last_usage_date: str
    record_id: str | None = field(default=None, repr=False)

    @classmethod
    def from_airtable_record(cls, record: Any) -> Self:
        """Creates an instance from a raw Airtable record."""
        fields = record.get("fields", {})
        return cls(
            record_id=record.get("id"),
            account_id=fields.get(FinOpsFields.ACCOUNT_ID),
            buyer_id=fields.get(FinOpsFields.BUYER_ID),
            agreement_id=fields.get(FinOpsFields.AGREEMENT_ID),
            entitlement_id=fields.get(FinOpsFields.ENTITLEMENT_ID),
            status=fields.get(FinOpsFields.STATUS),
            last_usage_date=fields.get(FinOpsFields.LAST_USAGE_DATE),
        )

    def to_airtable_fields(self) -> dict[str, Any]:
        """Convert the record to Airtable fields format."""
        field_mapping = {
            FinOpsFields.ACCOUNT_ID: self.account_id,
            FinOpsFields.BUYER_ID: self.buyer_id,
            FinOpsFields.AGREEMENT_ID: self.agreement_id,
            FinOpsFields.ENTITLEMENT_ID: self.entitlement_id,
            FinOpsFields.STATUS: self.status,
            FinOpsFields.LAST_USAGE_DATE: self.last_usage_date,
        }
        return {key: item_data for key, item_data in field_mapping.items() if item_data is not None}

    def is_new(self) -> bool:
        """Check if the record is new (not yet saved to Airtable)."""
        return self.record_id is None


class AccountMigrationFields(StrEnum):
    """Fields in the AWS Account Migration Airtable table."""

    SWO_SELLER = "SWO Seller"
    SWO_BUYER = "SWO Buyer"
    MASTERPAYER = "Masterpayer"
    MPT_CCO = "MPT CCO"
    AWS_ACCOUNT_EMAIL = "AWS account email"
    AWS_SUPPORT_TYPE = "AWS support type"
    SWO_SUPPORT_DISCOUNT = "SWO support discount"
    SWO_USAGE_DISCOUNT = "SWO usage discount"
    TECHNICAL_CONTACT_NAME = "Technical contact name"
    TECHNICAL_CONTACT_EMAIL = "Technical contact email"
    TECHNICAL_PHONE = "Technical phone"
    GROUP = "Group"
    BATCH = "Batch"
    MIGRATION_STATUS = "Migration status"
    MPT_ORDER_ID = "MPT Order ID"
    MPT_ORDER_STATUS = "MPT Order status"
    ORDER_CREATION_DATE = "Order creation date"
    CUSTOMER_ACCEPTED_DATE = "Customer accepted date"
    MIGRATION_COMPLETED_DATE = "Migration completed date"
    BILLING_TRANSFER_START_DATE = "Billing transfer start date"
    BATCH_GROUP_NUMBER = "Batch group number"
    ERROR = "Error"


class AccountMigrationStatus(StrEnum):
    """Lifecycle of a migration row in the AWS Account Migration table."""

    READY = "Ready"
    PROCESSING = "Processing"
    PENDING_NOTIFY_CUSTOMER = "Pending notify customer"
    MIGRATION_IN_PROGRESS = "Migration in progress"
    COMPLETED = "Completed"
    SERVICES_ONBOARDED = "Services onboarded"
    ERROR = "Error"
    FAILED = "Failed"


class AccountMigrationOrderStatus(StrEnum):
    """Status of the Marketplace order mirrored in the AWS Account Migration table."""

    DRAFT = "Draft"
    PROCESSING = "Processing"
    QUERYING = "Querying"
    COMPLETED = "Completed"
    FAILED = "Failed"


@dataclass
class AccountMigrationRecord:
    """Represent an AWS Account Migration record from Airtable."""

    swo_seller: str
    swo_buyer: str
    masterpayer: str
    mpt_cco: str
    aws_account_email: str
    aws_support_type: str
    technical_contact_name: str
    technical_contact_email: str
    group: str
    batch: str
    swo_support_discount: float | None = None
    swo_usage_discount: float | None = None
    technical_phone: str | None = None
    migration_status: str | None = None
    mpt_order_id: str | None = None
    mpt_order_status: str | None = None
    order_creation_date: str | None = None
    customer_accepted_date: str | None = None
    migration_completed_date: str | None = None
    billing_transfer_start_date: str | None = None
    batch_group_number: int | None = None
    error: str | None = None
    record_id: str | None = field(default=None, repr=False)

    @classmethod
    def from_airtable_record(cls, record: Any) -> Self:
        """Creates an instance from a raw Airtable record."""
        fields = record.get("fields", {})
        return cls(
            record_id=record.get("id"),
            swo_seller=fields.get(AccountMigrationFields.SWO_SELLER),
            swo_buyer=fields.get(AccountMigrationFields.SWO_BUYER),
            masterpayer=fields.get(AccountMigrationFields.MASTERPAYER),
            mpt_cco=fields.get(AccountMigrationFields.MPT_CCO),
            aws_account_email=fields.get(AccountMigrationFields.AWS_ACCOUNT_EMAIL),
            aws_support_type=fields.get(AccountMigrationFields.AWS_SUPPORT_TYPE),
            swo_support_discount=fields.get(AccountMigrationFields.SWO_SUPPORT_DISCOUNT),
            swo_usage_discount=fields.get(AccountMigrationFields.SWO_USAGE_DISCOUNT),
            technical_contact_name=fields.get(AccountMigrationFields.TECHNICAL_CONTACT_NAME),
            technical_contact_email=fields.get(AccountMigrationFields.TECHNICAL_CONTACT_EMAIL),
            technical_phone=fields.get(AccountMigrationFields.TECHNICAL_PHONE),
            group=fields.get(AccountMigrationFields.GROUP),
            batch=fields.get(AccountMigrationFields.BATCH),
            migration_status=fields.get(AccountMigrationFields.MIGRATION_STATUS),
            mpt_order_id=fields.get(AccountMigrationFields.MPT_ORDER_ID),
            mpt_order_status=fields.get(AccountMigrationFields.MPT_ORDER_STATUS),
            order_creation_date=fields.get(AccountMigrationFields.ORDER_CREATION_DATE),
            customer_accepted_date=fields.get(AccountMigrationFields.CUSTOMER_ACCEPTED_DATE),
            migration_completed_date=fields.get(AccountMigrationFields.MIGRATION_COMPLETED_DATE),
            billing_transfer_start_date=fields.get(
                AccountMigrationFields.BILLING_TRANSFER_START_DATE
            ),
            batch_group_number=fields.get(AccountMigrationFields.BATCH_GROUP_NUMBER),
            error=fields.get(AccountMigrationFields.ERROR),
        )

    def to_airtable_fields(self) -> dict[str, Any]:
        """Convert the record to Airtable fields format."""
        field_mapping = {
            AccountMigrationFields.SWO_SELLER: self.swo_seller,
            AccountMigrationFields.SWO_BUYER: self.swo_buyer,
            AccountMigrationFields.MASTERPAYER: self.masterpayer,
            AccountMigrationFields.MPT_CCO: self.mpt_cco,
            AccountMigrationFields.AWS_ACCOUNT_EMAIL: self.aws_account_email,
            AccountMigrationFields.AWS_SUPPORT_TYPE: self.aws_support_type,
            AccountMigrationFields.SWO_SUPPORT_DISCOUNT: self.swo_support_discount,
            AccountMigrationFields.SWO_USAGE_DISCOUNT: self.swo_usage_discount,
            AccountMigrationFields.TECHNICAL_CONTACT_NAME: self.technical_contact_name,
            AccountMigrationFields.TECHNICAL_CONTACT_EMAIL: self.technical_contact_email,
            AccountMigrationFields.TECHNICAL_PHONE: self.technical_phone,
            AccountMigrationFields.GROUP: self.group,
            AccountMigrationFields.BATCH: self.batch,
            AccountMigrationFields.MIGRATION_STATUS: self.migration_status,
            AccountMigrationFields.MPT_ORDER_ID: self.mpt_order_id,
            AccountMigrationFields.MPT_ORDER_STATUS: self.mpt_order_status,
            AccountMigrationFields.ORDER_CREATION_DATE: self.order_creation_date,
            AccountMigrationFields.CUSTOMER_ACCEPTED_DATE: self.customer_accepted_date,
            AccountMigrationFields.MIGRATION_COMPLETED_DATE: self.migration_completed_date,
            AccountMigrationFields.BILLING_TRANSFER_START_DATE: self.billing_transfer_start_date,
            AccountMigrationFields.BATCH_GROUP_NUMBER: self.batch_group_number,
            AccountMigrationFields.ERROR: self.error,
        }
        return {key: item_data for key, item_data in field_mapping.items() if item_data is not None}

    def is_new(self) -> bool:
        """Check if the record is new (not yet saved to Airtable)."""
        return self.record_id is None
