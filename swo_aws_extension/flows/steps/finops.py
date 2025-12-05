import logging

logger = logging.getLogger(__name__)


def create_finops_entitlement(ffc_client, account_id, buyer_id, logger_header):
    """
    Create a FinOps entitlement for the given account ID if it does not already exist.

    Args:
        ffc_client: The FinOps client instance.
        account_id: The account ID to create the entitlement for.
        buyer_id: The buyer ID associated with the entitlement.
        logger_header: The header for the logger to identify the source of the log message.
    """
    entitlement = ffc_client.get_entitlement_by_datasource_id(account_id)
    if entitlement:
        logger.info(
            "%s - Skipping - Entitlement already exists (%s) for account id %s",
            logger_header,
            entitlement["id"],
            account_id,
        )
    else:
        logger.info(
            "%s - Action - Creating entitlement for account id %s",
            logger_header,
            account_id,
        )
        entitlement = ffc_client.create_entitlement(buyer_id, account_id)
        logger.info(
            "%s - Action - Created entitlement %s for account id %s",
            logger_header,
            entitlement["id"],
            account_id,
        )
