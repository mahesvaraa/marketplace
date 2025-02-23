from enum import Enum


class RequestsParams(str, Enum):
    CREATE_SELL_ORDER_REQUEST = """
                    mutation CreateSellOrder($spaceId: String!, $tradeItems: [TradeOrderItem!]!, $paymentOptions: [PaymentItem!]!) {
                        createSellOrder(
                            spaceId: $spaceId
                            tradeItems: $tradeItems
                            paymentOptions: $paymentOptions
                        ) {
                            trade {
                                id
                                state
                                tradeId
                            }
                        }
                    }
                """
    UPDATE_SELL_ORDER_REQUEST = """
                mutation UpdateSellOrder($spaceId: String!, $tradeId: String!, $paymentOptions: [PaymentItem!]!) {
                    updateSellOrder(
                        spaceId: $spaceId
                        tradeId: $tradeId
                        paymentOptions: $paymentOptions
                    ) {
                        trade {
                            id
                            tradeId
                            state
                            category
                            createdAt
                            expiresAt
                            lastModifiedAt
                        }
                    }
                }
            """
    GET_SELLABLE_ITEMS_REQUEST = """
                query GetSellableItems($spaceId: String!, $limit: Int!, $offset: Int, $filterBy: MarketableItemFilter, $sortBy: MarketableItemSort) {
                    game(spaceId: $spaceId) {
                        id
                        viewer {
                            meta {
                                id
                                marketableItems(
                                    limit: $limit
                                    offset: $offset
                                    filterBy: $filterBy
                                    sortBy: $sortBy
                                    withMarketData: true
                                ) {
                                    nodes {
                                        item {
                                            id
                                            assetUrl
                                            itemId
                                            name
                                            tags
                                            type
                                        }
                                        marketData {
                                            id
                                            sellStats {
                                                paymentItemId
                                                lowestPrice
                                                highestPrice
                                                activeCount
                                            }
                                            lastSoldAt {
                                                paymentItemId
                                                price
                                                performedAt
                                            }
                                            buyStats {
                                                id
                                                paymentItemId
                                                lowestPrice
                                                highestPrice
                                                activeCount
                                            }
                                        }
                                    }
                                    totalCount
                                }
                            }
                        }
                    }
                }
            """
    GET_MARKETABLE_ITEMS_QUERY = """
                query GetMarketableItems($spaceId: String!, $limit: Int!, $offset: Int, $filterBy: MarketableItemFilter, $withOwnership: Boolean = true, $sortBy: MarketableItemSort) {
                    game(spaceId: $spaceId) {
                        id
                        marketableItems(
                            limit: $limit
                            offset: $offset
                            filterBy: $filterBy
                            sortBy: $sortBy
                            withMarketData: true
                        ) {
                            nodes {
                                item {
                                    id
                                    assetUrl
                                    itemId
                                    name
                                    tags
                                    type
                                    viewer @include(if: $withOwnership) {
                                        meta {
                                            id
                                            isOwned
                                            quantity
                                        }
                                    }
                                }
                                marketData {
                                    id
                                    sellStats {
                                        id
                                        paymentItemId
                                        lowestPrice
                                        highestPrice
                                        activeCount
                                    }
                                    buyStats {
                                        id
                                        paymentItemId
                                        lowestPrice
                                        highestPrice
                                        activeCount
                                    }
                                    lastSoldAt {
                                        id
                                        paymentItemId
                                        price
                                        performedAt
                                    }
                                }
                                viewer {
                                    meta {
                                        id
                                        activeTrade {
                                            id
                                            tradeId
                                            state
                                            category
                                            createdAt
                                            expiresAt
                                            lastModifiedAt
                                            failures
                                        }
                                    }
                                }
                            }
                            totalCount
                        }
                    }
                }
            """
    CANCEL_OLD_TRADE_QUERY = """
                mutation CancelOrder($spaceId: String!, $tradeId: String!) {
                    cancelOrder(spaceId: $spaceId, tradeId: $tradeId) {
                        trade {
                            id
                            tradeId
                            state
                            category
                            createdAt
                            expiresAt
                            lastModifiedAt
                            failures
                            tradeItems {
                                id
                                item {
                                    id
                                    assetUrl
                                    itemId
                                    name
                                    tags
                                    type
                                }
                            }
                            payment {
                                id
                                item {
                                    viewer {
                                        meta {
                                            id
                                            quantity
                                        }
                                    }
                                }
                                price
                                transactionFee
                            }
                        }
                    }
                }
            """
    GET_PENDING_TRADES_QUERY = """
                query GetTransactionsPending($spaceId: String!, $limit: Int!, $offset: Int) {
                    game(spaceId: $spaceId) {
                        id
                        viewer {
                            meta {
                                id
                                trades(
                                    limit: $limit
                                    offset: $offset
                                    filterBy: {states: [Created]}
                                    sortBy: {field: LAST_MODIFIED_AT}
                                ) {
                                    nodes {
                                        id
                                        tradeId
                                        state
                                        category
                                        createdAt
                                        expiresAt
                                        lastModifiedAt
                                        failures
                                        tradeItems {
                                            id
                                            item {
                                                id
                                                assetUrl
                                                itemId
                                                name
                                                tags
                                                type
                                            }
                                        }
                                        payment {
                                            id
                                            item {
                                                viewer {
                                                    meta {
                                                        id
                                                        quantity
                                                    }
                                                }
                                            }
                                            price
                                            transactionFee
                                        }
                                        paymentOptions {
                                            id
                                            item {
                                                viewer {
                                                    meta {
                                                        id
                                                        quantity
                                                    }
                                                }
                                            }
                                            price
                                            transactionFee
                                        }
                                        paymentProposal {
                                            id
                                            item {
                                                viewer {
                                                    meta {
                                                        id
                                                        quantity
                                                    }
                                                }
                                            }
                                            price
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            """

    CREATE_BUY_ORDER_REQUEST = """
        mutation CreateBuyOrder($spaceId: String!, $tradeItems: [TradeOrderItem!]!, $paymentProposal: PaymentItem!) {
            createBuyOrder(
                spaceId: $spaceId
                tradeItems: $tradeItems
                paymentProposal: $paymentProposal
            ) {
                trade {
                    id
                    state
                    tradeId
                }
            }
        }
    """
