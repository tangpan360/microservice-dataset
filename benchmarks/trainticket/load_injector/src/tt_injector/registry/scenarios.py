from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tt_injector.scenarios import catalog


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    scenario_id: str
    title: str
    description: str
    handler: Callable


SCENARIOS: dict[str, ScenarioSpec] = {
    "browseBasic": ScenarioSpec(
        scenario_id="browseBasic",
        title="基础浏览",
        description="查询余票，模拟轻量浏览行为。",
        handler=catalog.browse_basic,
    ),
    "browsePlusRoute": ScenarioSpec(
        scenario_id="browsePlusRoute",
        title="浏览加路线",
        description="查询路线、并行余票和食物，模拟扩展浏览行为。",
        handler=catalog.browse_plus_route,
    ),
    "browseAdvanced": ScenarioSpec(
        scenario_id="browseAdvanced",
        title="高级查询",
        description="查询高级路线规划，混合 cheapest 与 quickest。",
        handler=catalog.browse_advanced,
    ),
    "browseAdvancedAlt": ScenarioSpec(
        scenario_id="browseAdvancedAlt",
        title="高级查询补充",
        description="查询另一组高级规划类型或 OD 组合。",
        handler=catalog.browse_advanced_alt,
    ),
    "orderRefresh": ScenarioSpec(
        scenario_id="orderRefresh",
        title="订单刷新",
        description="刷新用户订单列表，模拟高频轻量查看行为。",
        handler=catalog.order_refresh,
    ),
    "contactLookup": ScenarioSpec(
        scenario_id="contactLookup",
        title="联系人查询",
        description="查询常用乘车人或联系人。",
        handler=catalog.contact_lookup,
    ),
    "preserveAndPay": ScenarioSpec(
        scenario_id="preserveAndPay",
        title="下单并支付",
        description="创建订单并完成支付。",
        handler=catalog.preserve_and_pay,
    ),
    "preserveWithFood": ScenarioSpec(
        scenario_id="preserveWithFood",
        title="带餐食下单",
        description="创建带餐食订单并完成支付。",
        handler=catalog.preserve_with_food,
    ),
    "preserveWithAssurance": ScenarioSpec(
        scenario_id="preserveWithAssurance",
        title="带保险下单",
        description="创建带保险订单并完成支付。",
        handler=catalog.preserve_with_assurance,
    ),
    "payCollectEnter": ScenarioSpec(
        scenario_id="payCollectEnter",
        title="支付取票进站",
        description="准备订单状态并执行进站流程。",
        handler=catalog.pay_collect_enter,
    ),
    "cancelFlow": ScenarioSpec(
        scenario_id="cancelFlow",
        title="取消流程",
        description="准备可取消订单并执行取消。",
        handler=catalog.cancel_flow,
    ),
    "rebookFlow": ScenarioSpec(
        scenario_id="rebookFlow",
        title="改签流程",
        description="准备订单并改签到新车次。",
        handler=catalog.rebook_flow,
    ),
    "consignFlow": ScenarioSpec(
        scenario_id="consignFlow",
        title="托运流程",
        description="准备订单并执行托运。",
        handler=catalog.consign_flow,
    ),
    "adminObserve": ScenarioSpec(
        scenario_id="adminObserve",
        title="管理观察",
        description="查询基础价格和基础配置。",
        handler=catalog.admin_observe,
    ),
    "foodBrowseOnly": ScenarioSpec(
        scenario_id="foodBrowseOnly",
        title="餐食浏览",
        description="查询并浏览餐食结果，补充轻量餐食链路。",
        handler=catalog.food_browse_only,
    ),
    "postPurchaseOrderView": ScenarioSpec(
        scenario_id="postPurchaseOrderView",
        title="购后订单查看",
        description="准备已支付订单后刷新订单列表。",
        handler=catalog.post_purchase_order_view,
    ),
}
