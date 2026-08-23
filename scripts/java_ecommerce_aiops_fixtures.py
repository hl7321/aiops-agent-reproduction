"""十套稳定、合成且可跨 CLS、Alertmanager 与 SOP 关联的 Java 电商故障。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TypeAlias

LogRecord: TypeAlias = dict[str, str]
AlertPayload: TypeAlias = dict[str, object]


@dataclass(frozen=True, slots=True)
class JavaEcommerceIncident:
    incident_id: str
    trace_id: str
    service: str
    alertname: str
    sop_id: str
    logger: str
    exception: str
    dependency: str
    metric: str
    threshold: str
    symptom: str
    root_cause: str
    investigation: tuple[str, ...]
    recovery: tuple[str, ...]
    verification: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SopDocument:
    filename: str
    content: str
    metadata: dict[str, str]


JAVA_ECOMMERCE_INCIDENTS: tuple[JavaEcommerceIncident, ...] = (
    JavaEcommerceIncident(
        incident_id="java-ecom-001-payment-gateway-timeout",
        trace_id="4a000000000000000000000000000001",
        service="payment-service",
        alertname="PaymentGatewayTimeoutHigh",
        sop_id="sop-payment-gateway-timeout",
        logger="com.example.payment.gateway.PaymentGatewayClient",
        exception="java.net.SocketTimeoutException",
        dependency="payment-gateway",
        metric="payment_gateway_timeout_rate",
        threshold="> 5% for 5m",
        symptom="支付请求在调用外部支付网关时超时，结算成功率下降。",
        root_cause="支付网关响应时间超过客户端读取超时，重试放大了等待请求。",
        investigation=("按 trace_id 查询网关调用耗时", "核对超时率与上游状态页"),
        recovery=("限制重试并启用支付降级提示", "与支付网关确认容量和延迟"),
        verification=("支付超时率恢复到 1% 以下", "抽样支付链路成功且无重复扣款"),
    ),
    JavaEcommerceIncident(
        incident_id="java-ecom-002-inventory-lock-wait",
        trace_id="4a000000000000000000000000000002",
        service="inventory-service",
        alertname="InventoryDatabaseLockWaitHigh",
        sop_id="sop-inventory-lock-wait",
        logger="com.example.inventory.repository.StockRepository",
        exception="org.springframework.dao.CannotAcquireLockException",
        dependency="inventory-mysql",
        metric="inventory_lock_wait_seconds",
        threshold="> 3s p95 for 10m",
        symptom="库存预占请求阻塞，部分订单长时间停留在待确认状态。",
        root_cause="热点 SKU 更新事务持锁过久，导致并发预占等待数据库行锁。",
        investigation=("定位热点 SKU 与长事务", "核对锁等待图和慢 SQL"),
        recovery=("终止异常长事务", "按 SKU 顺序化批量更新并缩短事务范围"),
        verification=("锁等待 p95 低于 500ms", "库存预占吞吐恢复且无超卖"),
    ),
    JavaEcommerceIncident(
        incident_id="java-ecom-003-order-db-pool-exhausted",
        trace_id="4a000000000000000000000000000003",
        service="order-service",
        alertname="OrderDatabasePoolExhausted",
        sop_id="sop-order-db-pool-exhausted",
        logger="com.example.order.config.HikariPoolMonitor",
        exception="java.sql.SQLTransientConnectionException",
        dependency="order-mysql",
        metric="hikaricp_connections_pending",
        threshold="> 20 for 5m",
        symptom="创建订单接口排队并返回数据库连接获取超时。",
        root_cause="慢查询占用连接时间过长，连接池可用连接被耗尽。",
        investigation=("检查 Hikari 活跃与等待连接", "按 trace_id 定位慢查询"),
        recovery=("停止高成本查询并恢复连接", "优化索引后再评估连接池上限"),
        verification=("等待连接数归零", "订单创建延迟和错误率恢复基线"),
    ),
    JavaEcommerceIncident(
        incident_id="java-ecom-004-cart-redis-latency",
        trace_id="4a000000000000000000000000000004",
        service="cart-service",
        alertname="CartRedisLatencyHigh",
        sop_id="sop-cart-redis-latency",
        logger="com.example.cart.cache.RedisCartRepository",
        exception="io.lettuce.core.RedisCommandTimeoutException",
        dependency="cart-redis",
        metric="redis_command_duration_seconds",
        threshold="> 250ms p99 for 5m",
        symptom="购物车读取与更新明显变慢，部分请求触发 Redis 命令超时。",
        root_cause="Redis 热 key 与大 value 导致单线程事件循环延迟升高。",
        investigation=("检查慢日志和热 key", "核对 value 大小与连接事件循环延迟"),
        recovery=("拆分热 key 并限制 value 大小", "必要时迁移热点分片"),
        verification=("Redis p99 低于 50ms", "购物车操作无超时且数据一致"),
    ),
    JavaEcommerceIncident(
        incident_id="java-ecom-005-checkout-circuit-open",
        trace_id="4a000000000000000000000000000005",
        service="api-gateway",
        alertname="CheckoutCircuitBreakerOpen",
        sop_id="sop-checkout-circuit-open",
        logger="com.example.gateway.filter.CheckoutCircuitBreakerFilter",
        exception="io.github.resilience4j.circuitbreaker.CallNotPermittedException",
        dependency="checkout-service",
        metric="checkout_circuit_open_total",
        threshold="> 50 opens in 5m",
        symptom="网关拒绝新的结算调用并返回可恢复的服务不可用提示。",
        root_cause="下游结算错误率越过熔断阈值，熔断器持续处于 OPEN。",
        investigation=("核对熔断状态转换", "按 trace_id 检查下游原始错误"),
        recovery=("修复下游后小流量 half-open 探测", "避免直接强制关闭熔断保护"),
        verification=("熔断器稳定回到 CLOSED", "结算成功率恢复且下游无过载"),
    ),
    JavaEcommerceIncident(
        incident_id="java-ecom-006-promotion-cpu-saturation",
        trace_id="4a000000000000000000000000000006",
        service="promotion-service",
        alertname="PromotionCpuSaturation",
        sop_id="sop-promotion-cpu-saturation",
        logger="com.example.promotion.engine.RuleEvaluationEngine",
        exception="java.util.concurrent.RejectedExecutionException",
        dependency="promotion-rule-engine",
        metric="process_cpu_usage",
        threshold="> 90% for 10m",
        symptom="促销规则计算延迟升高，线程池开始拒绝新任务。",
        root_cause="高复杂度规则组合触发过量计算，CPU 长时间饱和。",
        investigation=("采集安全 CPU profile", "定位高成本规则与拒绝任务计数"),
        recovery=("停用异常规则版本", "限制单请求规则组合并扩容实例"),
        verification=("CPU 使用率低于 70%", "促销计算延迟与拒绝数恢复"),
    ),
    JavaEcommerceIncident(
        incident_id="java-ecom-007-order-kafka-lag",
        trace_id="4a000000000000000000000000000007",
        service="order-event-consumer",
        alertname="OrderEventConsumerLagHigh",
        sop_id="sop-order-kafka-lag",
        logger="com.example.order.consumer.OrderEventListener",
        exception="org.apache.kafka.common.errors.TimeoutException",
        dependency="order-events-kafka",
        metric="kafka_consumer_group_lag",
        threshold="> 10000 records for 10m",
        symptom="订单事件积压，库存与履约状态更新出现延迟。",
        root_cause="消费端批处理下游超时，分区消费速率低于生产速率。",
        investigation=("按分区检查 lag 和消费速率", "定位批处理下游超时"),
        recovery=("修复下游后逐步扩容消费者", "控制回放速率避免二次过载"),
        verification=("lag 持续下降至 100 以下", "订单状态最终一致且无重复副作用"),
    ),
    JavaEcommerceIncident(
        incident_id="java-ecom-008-product-search-timeout",
        trace_id="4a000000000000000000000000000008",
        service="product-search-service",
        alertname="ProductSearchElasticsearchTimeout",
        sop_id="sop-product-search-timeout",
        logger="com.example.search.client.ProductSearchClient",
        exception="java.net.SocketTimeoutException",
        dependency="product-elasticsearch",
        metric="elasticsearch_query_duration_seconds",
        threshold="> 2s p95 for 5m",
        symptom="商品搜索响应超时，分类页出现空结果或降级结果。",
        root_cause="高基数字段聚合造成 Elasticsearch 查询与 heap 压力上升。",
        investigation=("检查慢查询与 rejected 指标", "核对节点 heap 和查询 DSL"),
        recovery=("禁用高成本聚合", "优化 mapping/查询并恢复降级缓存"),
        verification=("查询 p95 低于 500ms", "搜索结果完整且节点 heap 稳定"),
    ),
    JavaEcommerceIncident(
        incident_id="java-ecom-009-auth-jwk-refresh-failure",
        trace_id="4a000000000000000000000000000009",
        service="auth-service",
        alertname="AuthJwkRefreshFailure",
        sop_id="sop-auth-jwk-refresh-failure",
        logger="com.example.auth.jwk.JwkSetRefresher",
        exception="com.nimbusds.jose.RemoteKeySourceException",
        dependency="identity-provider-jwks",
        metric="jwk_refresh_failures_total",
        threshold="> 5 failures in 5m",
        symptom="JWK 刷新失败，新签发 token 的验证开始出现失败。",
        root_cause="身份提供方 JWK endpoint 返回异常，缓存 key 即将过期。",
        investigation=("检查 JWK endpoint 状态和证书", "核对缓存 key 到期时间"),
        recovery=("恢复 endpoint 连通性", "在安全期限内使用已验证缓存 key"),
        verification=("JWK 刷新连续成功", "新旧 token 验证均符合预期"),
    ),
    JavaEcommerceIncident(
        incident_id="java-ecom-010-fulfillment-vendor-503",
        trace_id="4a00000000000000000000000000000a",
        service="fulfillment-service",
        alertname="FulfillmentVendorUnavailable",
        sop_id="sop-fulfillment-vendor-503",
        logger="com.example.fulfillment.vendor.VendorApiClient",
        exception="org.springframework.web.client.HttpServerErrorException$ServiceUnavailable",
        dependency="fulfillment-vendor-api",
        metric="vendor_http_503_rate",
        threshold="> 10% for 5m",
        symptom="履约请求收到供应商 503，发货单创建延迟。",
        root_cause="外部供应商维护窗口内容量不足并返回 Service Unavailable。",
        investigation=("按 trace_id 核对 503 响应率", "检查供应商状态通知与重试队列"),
        recovery=("暂停即时重试并进入有界队列", "供应商恢复后限速回放"),
        verification=("503 比例恢复到 1% 以下", "积压发货单清空且无重复创建"),
    ),
)


def build_java_cls_records(
    region: str, *, now: datetime | None = None
) -> tuple[LogRecord, ...]:
    timestamp = _utc(now).isoformat().replace("+00:00", "Z")
    return tuple(
        {
            "region": region,
            "profile": "java-ecommerce",
            "incident_id": incident.incident_id,
            "trace_id": incident.trace_id,
            "traceId": incident.trace_id,
            "service": incident.service,
            "alertname": incident.alertname,
            "sop_id": incident.sop_id,
            "logger": incident.logger,
            "exception": incident.exception,
            "dependency": incident.dependency,
            "metric": incident.metric,
            "threshold": incident.threshold,
            "rootCause": incident.root_cause,
            "investigation": " | ".join(incident.investigation),
            "recovery": " | ".join(incident.recovery),
            "verification": " | ".join(incident.verification),
            "severity": "critical",
            "level": "ERROR",
            "timestamp": timestamp,
            "message": incident.symptom,
        }
        for incident in JAVA_ECOMMERCE_INCIDENTS
    )


def build_java_alertmanager_alerts(
    *, now: datetime | None = None, active_for: timedelta = timedelta(hours=2)
) -> tuple[AlertPayload, ...]:
    starts_at = _utc(now)
    ends_at = starts_at + active_for
    return tuple(
        {
            "labels": {
                "alertname": incident.alertname,
                "service": incident.service,
                "severity": "critical",
                "incident_id": incident.incident_id,
                "trace_id": incident.trace_id,
                "sop_id": incident.sop_id,
                "profile": "java-ecommerce",
            },
            "annotations": {
                "summary": incident.symptom,
                "description": (
                    f"synthetic demo: {incident.exception}; dependency={incident.dependency}; "
                    f"metric={incident.metric}; threshold={incident.threshold}"
                ),
                "rootCause": incident.root_cause,
                "investigation": " | ".join(incident.investigation),
                "recovery": " | ".join(incident.recovery),
                "verification": " | ".join(incident.verification),
            },
            "startsAt": starts_at.isoformat().replace("+00:00", "Z"),
            "endsAt": ends_at.isoformat().replace("+00:00", "Z"),
            "generatorURL": "http://127.0.0.1/synthetic/java-ecommerce",
        }
        for incident in JAVA_ECOMMERCE_INCIDENTS
    )


def build_java_sop_documents() -> tuple[SopDocument, ...]:
    return tuple(
        SopDocument(
            filename=f"{incident.sop_id}.md",
            content=_build_sop_markdown(incident),
            metadata={
                "knowledgeType": "aiops-sop",
                "incidentId": incident.incident_id,
                "traceId": incident.trace_id,
                "service": incident.service,
                "alertname": incident.alertname,
                "sopId": incident.sop_id,
            },
        )
        for incident in JAVA_ECOMMERCE_INCIDENTS
    )


def _build_sop_markdown(incident: JavaEcommerceIncident) -> str:
    metadata = (
        f"- knowledgeType: aiops-sop\n"
        f"- incident_id: {incident.incident_id}\n"
        f"- trace_id: {incident.trace_id}\n"
        f"- service: {incident.service}\n"
        f"- alertname: {incident.alertname}\n"
        f"- sop_id: {incident.sop_id}\n"
        f"- logger: {incident.logger}\n"
        f"- exception: {incident.exception}\n"
        f"- dependency: {incident.dependency}\n"
        f"- metric: {incident.metric}\n"
        f"- threshold: {incident.threshold}"
    )
    return (
        f"# Java 电商故障 SOP：{incident.alertname}\n\n"
        "> 本文仅用于合成 AIOps 演示，不包含客户数据或真实凭据。\n\n"
        f"## 关联信息\n\n{metadata}\n\n"
        f"## 故障症状\n\n{incident.symptom}\n\n"
        f"## 根因\n\n{incident.root_cause}\n\n"
        f"## 排查步骤\n\n{_numbered(incident.investigation)}\n\n"
        f"## 恢复步骤\n\n{_numbered(incident.recovery)}\n\n"
        f"## 验证步骤\n\n{_numbered(incident.verification)}\n"
    )


def _numbered(items: tuple[str, ...]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _utc(value: datetime | None) -> datetime:
    selected = value or datetime.now(timezone.utc)
    if selected.tzinfo is None:
        raise ValueError("时间必须包含时区")
    return selected.astimezone(timezone.utc)
