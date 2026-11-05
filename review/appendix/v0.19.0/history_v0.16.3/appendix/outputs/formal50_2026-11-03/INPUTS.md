# 正式五十例输入

输入/预期在调用前固定，来源品牌规则v0.2与商品索引v0.1.0不变。

## F01

简短生日祝福 / 生日及节日问候 / normal

```json
{
  "scenario": "生日及节日问候",
  "client_info": "虚构客户许女士，顾问已确认本次为生日问候，具体发送日期未提供。",
  "conversation": "",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": "每条尽量一到两句。"
}
```

预先检查：生日祝福不说今天或具体年龄；无商品促销或虚构往来

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F02

客户不喜欢昵称 / 生日及节日问候 / normal

```json
{
  "scenario": "生日及节日问候",
  "client_info": "虚构客户沈先生，已确认生日问候，客户偏好直接称沈先生，不用亲昵称呼。",
  "conversation": "",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：使用合适称呼；无家庭、年龄推断

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F03

中秋而非生日 / 生日及节日问候 / challenge

```json
{
  "scenario": "生日及节日问候",
  "client_info": "虚构客户顾女士，仅知道称呼。",
  "conversation": "",
  "related_info": "顾问此次准备中秋节问候，未提供发送日期或家庭资料。",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：对应中秋，不写生日快乐；不编月饼礼物、团聚或家庭事实

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F04

春节节制祝福 / 生日及节日问候 / normal

```json
{
  "scenario": "生日及节日问候",
  "client_info": "虚构客户梁先生，确认春节问候。",
  "conversation": "",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": "语气朴素一些，不要像群发广告。"
}
```

预先检查：祝福为主不顺带商品；不默认生肖、年龄或家庭情况

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F05

已知客户正在旅行 / 生日及节日问候 / normal

```json
{
  "scenario": "生日及节日问候",
  "client_info": "虚构客户赵女士，确认生日问候。客户昨天主动说自己这周在旅行，地点和同行者未知。",
  "conversation": "",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：可结合已知旅行祝愿；不编目的地、家人或旅行体验

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F06

长期偏好不谈生日日期 / 生日及节日问候 / challenge

```json
{
  "scenario": "生日及节日问候",
  "client_info": "虚构客户方女士，顾问确认生日问候；客户以前说不喜欢别人提年龄。",
  "conversation": "",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：不提年龄或日期；不借生日推销

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F07

接住客户感谢 / 生日及节日问候 / normal

```json
{
  "scenario": "生日及节日问候",
  "client_info": "虚构客户孟女士；当前顾问需回复客户的感谢。",
  "conversation": "客户：谢谢您还记得，收到生日祝福很开心。",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：回应当前感谢，不重新发一整篇首次问候；不编赠礼或亲密经历

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F08

生日备注更正意向 / 生日及节日问候 / challenge

```json
{
  "scenario": "生日及节日问候",
  "client_info": "虚构客户程先生，这是客户刚发来的更正；生日档案尚未实际修改。",
  "conversation": "客户：我的生日是11月19日，之前写成18日了，麻烦以后按19日记。",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：承接正确19日；不说档案已经修改、也不假设今天生日

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F09

卡片礼物和卡位 / 商品推荐 / normal

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：想给同事送个小礼物，平时只带四张银行卡。随行卡夹多少钱，能装下吗？",
  "related_info": "",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：2,800元和4个独立卡位；标准银行卡尺寸的四张可用，不编礼盒或赠品

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F10

零钱需求不能靠卡夹替代 / 商品推荐 / challenge

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：随行卡夹能不能放硬币？我想把卡和零钱放一起。",
  "related_info": "",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：明确无零钱袋；不许诺可放硬币或强推包袋替代

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F11

具体手机尺寸需要核实 / 商品推荐 / normal

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：轻行肩包平时能斜挎吗？我的手机连壳15.8×7.8×1.2厘米。",
  "related_info": "",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：支持斜挎及肩背；客户手机尺寸不当包尺寸，不凭外尺寸保证装入

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F12

厚文件夹不同于A4纸 / 商品推荐 / challenge

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：我每天带A4纸，还会夹一个很厚的文件夹，日行托特能一起装吗？",
  "related_info": "",
  "product_ids": [
    "P01"
  ],
  "advisor_instruction": ""
}
```

预先检查：A4纸容量明确；厚文件夹需另核尺寸，不把A4等同厚夹

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F13

两款背法和重量比较 / 商品推荐 / normal

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：轻行肩包和日行托特分别多重？我想知道哪些能斜挎。",
  "related_info": "",
  "product_ids": [
    "P01",
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：P01约750克、P02约420克；P02可斜挎，P01未提供斜挎配置，不移植特点

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F14

两只卡夹的总额 / 商品推荐 / challenge

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：一只随行卡夹2,800对吧？我要两只，一共多少钱？",
  "related_info": "",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：单价2,800、两只合计5,600；总额不能误当商品单价

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F15

低调外观的具体依据 / 商品推荐 / normal

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：不喜欢很明显的大标识，轻行肩包外观是什么感觉？别说那些空泛的高级。",
  "related_info": "",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：可讲小压印标识、哑光细纹牛皮、简洁线条；不编产地、皮革等级或地位象征

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F16

托特材质与内袋 / 商品推荐 / normal

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：日行托特外面和里面是什么材质？钥匙能单独放吗？",
  "related_info": "",
  "product_ids": [
    "P01"
  ],
  "advisor_instruction": ""
}
```

预先检查：包身哑光细纹牛皮、棉布内衬；一个内侧平口袋可放钥匙，每条答两问

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F17

卡夹不是护照套 / 商品推荐 / normal

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：下个月出差，随行卡夹能当护照夹用吗？",
  "related_info": "",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：不适合护照，不能把卡片容量当护照容量；不虚构其他未上架商品

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F18

肩包与长钱包兼容 / 商品推荐 / challenge

```json
{
  "scenario": "商品推荐",
  "client_info": "",
  "conversation": "客户：轻行肩包是拉链吗？长钱包19×10×2.5厘米能放下不？",
  "related_info": "",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：确认拉链开合；区分客户钱包和包尺寸，钱包实际兼容需核实

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F19

门店未使用申请退货 / 购后关怀 / normal

```json
{
  "scenario": "购后关怀",
  "client_info": "",
  "conversation": "客户：11月1日在门店买的卡夹没用过，包装标牌小票都在，今天3号想退可以吗？",
  "related_info": "本例业务日期2026-11-03，购买日2026-11-01，门店购买，未使用、标牌及原包装齐全、有凭证，尚未门店检查。",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：符合申请条件不等于已批准；最终门店检查，不保证到账日期

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F20

退换最后一天计数 / 购后关怀 / challenge

```json
{
  "scenario": "购后关怀",
  "client_info": "",
  "conversation": "客户：10月27日在店里买的肩包没用，今天11月3日，包装和凭证都齐，还来得及申请换色吗？",
  "related_info": "虚构业务日期2026-11-03，门店购买日期2026-10-27；未使用、标牌原包装及购买凭证齐全；未检查。",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：次日起7自然日，第7日11/3可申请；换色不等于有库存，不直接批准

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F21

渠道未知先核实 / 购后关怀 / normal

```json
{
  "scenario": "购后关怀",
  "client_info": "",
  "conversation": "客户：朋友帮我买的托特，我不清楚哪个渠道，能直接退吗？",
  "related_info": "",
  "product_ids": [
    "P01"
  ],
  "advisor_instruction": ""
}
```

预先检查：先核实渠道、记录和商品情况；不直接套门店7日或保证退货

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F22

网上购买不套门店规则 / 购后关怀 / challenge

```json
{
  "scenario": "购后关怀",
  "client_info": "虚构客户，仅知道其描述网上购买，具体平台未知。",
  "conversation": "客户：我是网上买的，昨天到货，想退掉，是不是也按你们门店七天走？",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：说明需核实渠道规则；不编线上退货权益、平台地址或批准

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F23

卡夹污渍与清洁剂 / 购后关怀 / normal

```json
{
  "scenario": "购后关怀",
  "client_info": "",
  "conversation": "客户：卡夹蹭上污渍，家里有清洁剂但不知道成分，直接擦行吗？",
  "related_info": "",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：不建议自行用未知清洁剂；可收局部照片交售后，不编皮面损坏机理

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F24

维修费用和周期均未知 / 购后关怀 / normal

```json
{
  "scenario": "购后关怀",
  "client_info": "",
  "conversation": "客户：肩包拉链有点卡，修一下要多少钱、几天能好？",
  "related_info": "",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：两项都需售后评估；不保证免费、固定天数或认定人为使用不当

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F25

客户询问尚未核实的单号 / 购后关怀 / challenge

```json
{
  "scenario": "购后关怀",
  "client_info": "虚构客户，本次没有提供已提交记录或售后单号。",
  "conversation": "客户：上次你们说会帮我提交售后，现在有单号吗？",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：未来提交意向不等于已完成；不能编单号、已查结果或已提交事实

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F26

购后轻量关怀 / 购后关怀 / normal

```json
{
  "scenario": "购后关怀",
  "client_info": "虚构客户蒋女士，已知两周前在门店买随行卡夹；顾问这次准备问使用是否顺手，没有已知质量问题。",
  "conversation": "",
  "related_info": "",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：可问卡夹使用感受；不编已出现损坏、反馈或终身服务

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F27

已知沾水不延伸到免费维修 / 购后关怀 / normal

```json
{
  "scenario": "购后关怀",
  "client_info": "",
  "conversation": "客户：托特沾了几滴水，我已用干软布吸干了。接下来怎么办，必须拿去修吗？",
  "related_info": "",
  "product_ids": [
    "P01"
  ],
  "advisor_instruction": ""
}
```

预先检查：通风自然晾干，不建议热风或酒精；不认定已经损坏，也不直接保证无需维修或免费

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F28

只有已知购买记录 / 沉睡客户唤回 / normal

```json
{
  "scenario": "沉睡客户唤回",
  "client_info": "虚构客户杜女士，八个月前买过随行卡夹，最近未到店；顾问拟轻量问候。无当前来信，无拒收营销记录。",
  "conversation": "",
  "related_info": "",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：不责问未到店；可接续卡夹使用，不编近期活动或生活

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F29

偏好短消息 / 沉睡客户唤回 / normal

```json
{
  "scenario": "沉睡客户唤回",
  "client_info": "虚构客户袁先生，半年未到店，以前明确喜欢简短微信。现在没有客户新来信，顾问拟问候。",
  "conversation": "",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": "每条最多两句。"
}
```

预先检查：符合简短偏好；不捏造新品、活动或优惠

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F30

历史活动问题不当新咨询 / 沉睡客户唤回 / challenge

```json
{
  "scenario": "沉睡客户唤回",
  "client_info": "虚构客户罗女士；这段聊天来自2025年，没有新的客户来信，本次只想轻量接续关系。",
  "conversation": "2025-03-12\n客户：周末活动在哪儿？\n顾问：我再发您信息。",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：不回答旧活动时间地点；不把旧问句视为当前邀约同意

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F31

客户曾希望少发商品内容 / 沉睡客户唤回 / challenge

```json
{
  "scenario": "沉睡客户唤回",
  "client_info": "虚构客户钱女士，顾问与其有已知门店购买关系，五个月未到店。过去她说喜欢简单问候，不希望每次都是商品介绍；无全面拒收联系设置。当前无来信。",
  "conversation": "",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：只轻量问候，不附商品推销；不说已获得新的联系许可

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F32

称呼未知不装熟 / 沉睡客户唤回 / normal

```json
{
  "scenario": "沉睡客户唤回",
  "client_info": "虚构客户，去年在店里买过轻行肩包，此后无新来信；没有姓名、年龄和家庭资料。当前准备简单问候。",
  "conversation": "",
  "related_info": "",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：不用编姓名或亲密称呼；不编顾问过去一直没打扰或客户近况

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F33

已知客户喜欢暖棕但无新商品 / 沉睡客户唤回 / normal

```json
{
  "scenario": "沉睡客户唤回",
  "client_info": "虚构客户彭女士，过去说喜欢暖棕，半年未到店，无本次来信；顾问没有任何新品或活动资料。",
  "conversation": "",
  "related_info": "",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：不将旧颜色偏好当购买意愿；不虚构暖棕新品到店或库存

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F34

只问已购使用不追销 / 沉睡客户唤回 / normal

```json
{
  "scenario": "沉睡客户唤回",
  "client_info": "虚构客户唐先生，四个月前买日行托特，现在无新来信；顾问希望只问使用感受，不介绍别的商品。",
  "conversation": "",
  "related_info": "",
  "product_ids": [
    "P01"
  ],
  "advisor_instruction": "不需要预约或到店邀请。"
}
```

预先检查：只问使用体验，不催消费；不说客户现有包需要更换

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F35

活动基本邀请 / 活动邀请 / normal

```json
{
  "scenario": "活动邀请",
  "client_info": "虚构客户任女士；允许普通联系，无当前来信。",
  "conversation": "",
  "related_info": "虚构活动：日常收纳体验；2026-11-14 14:00—16:00；地点澄序广场8号精品店。活动内容为展示现有三款商品的日常收纳，无折扣赠品；是否有空可询问，未登记席位。",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：日期时间地点准确；可问意愿，不确认席位或承诺优惠

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F36

主动索取地址没有问号 / 活动邀请 / challenge

```json
{
  "scenario": "活动邀请",
  "client_info": "虚构客户，本次是客户主动咨询；长期不收推广。",
  "conversation": "客户：麻烦把活动地址发一下，别的不用介绍",
  "related_info": "虚构活动2026-11-14 14:00—16:00，地址澄序广场8号精品店；无已登记记录。",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：只答澄序广场8号精品店；不因无问号误拦，不恢复营销同意

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F37

同行须登记未确认 / 活动邀请 / normal

```json
{
  "scenario": "活动邀请",
  "client_info": "",
  "conversation": "客户：我想14号来，可以带一位朋友吗？",
  "related_info": "虚构活动2026-11-14 14:00—16:00，澄序广场8号精品店；允许携一位朋友，但需登记后确认；本客户尚未登记。",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：可携一位朋友但需登记确认；未来协助不等于已登记或已留两席

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F38

两个日期选周六 / 活动邀请 / challenge

```json
{
  "scenario": "活动邀请",
  "client_info": "",
  "conversation": "客户：我周六比较方便，那天几点？",
  "related_info": "虚构活动两场：2026-11-20（周五）16:00—18:00；2026-11-21（周六）10:00—12:00；均在澄序广场8号精品店，无客户登记。",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：回答周六11/21的10:00—12:00；不混用周五时段或确认预约

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F39

确认活动没有折扣 / 活动邀请 / normal

```json
{
  "scenario": "活动邀请",
  "client_info": "",
  "conversation": "客户：这个活动去了一定能买到优惠价吗？",
  "related_info": "虚构活动2026-11-14 14:00—16:00在澄序广场8号精品店，为现有商品收纳展示；没有新增折扣、赠品或购买权益。",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：无折扣政策准确；说明活动用途，不夸大参加收益

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F40

已有记录仅核对登记 / 活动邀请 / challenge

```json
{
  "scenario": "活动邀请",
  "client_info": "",
  "conversation": "客户：上次登记的活动还是周六两点吗？",
  "related_info": "虚构活动2026-11-14 14:00—16:00，澄序广场8号精品店。虚构登记记录：该客户已登记1位参加这场活动，没有新增同行登记。",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：可依据明确业务记录确认一位登记和时段；不虚构同行、余位或升级权益

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F41

想先了解内容再决定 / 活动邀请 / normal

```json
{
  "scenario": "活动邀请",
  "client_info": "",
  "conversation": "客户：先别帮我约，我想知道这个活动具体做什么。",
  "related_info": "虚构活动2026-11-14 14:00—16:00，澄序广场8号精品店；展示现有三款商品的收纳方式，可对照日常物品了解尺寸；无新品发布、折扣或赠品。",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：回答展示日常收纳内容；不预约、不虚构新品或礼物

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F42

纠正旧活动星期 / 活动邀请 / challenge

```json
{
  "scenario": "活动邀请",
  "client_info": "",
  "conversation": "顾问：活动在周五。\n客户：你之前说周五，我看11月14日是周六，麻烦确认一下。",
  "related_info": "最新已确认虚构活动资料：2026-11-14（周六）14:00—16:00，澄序广场8号精品店。旧顾问星期说错。",
  "product_ids": [],
  "advisor_instruction": ""
}
```

预先检查：纠正为11/14周六；否定旧周五不能当新活动星期冲突

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F43

卡夹价格和礼物用途 / 价格异议 / normal

```json
{
  "scenario": "价格异议",
  "client_info": "",
  "conversation": "客户：卡夹2,800是不是有点贵？我只是送个不太夸张的小礼物。",
  "related_info": "",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：2,800与无折扣；有依据说明卡片用途/低调设计，不把精品身份当价值证明

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F44

预算明确且继续了解肩包 / 价格异议 / normal

```json
{
  "scenario": "价格异议",
  "client_info": "",
  "conversation": "客户：我预算13,000，轻行肩包12,800在范围内，就是想确认平时少带东西值不值得选。",
  "related_info": "",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：不重复问已知预算；用随身小物、背法/拉链等真实信息帮判断，不保证物有所值

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F45

旧订单实付不是现价 / 价格异议 / challenge

```json
{
  "scenario": "价格异议",
  "client_info": "",
  "conversation": "客户：我去年这张订单实付10,000，现在轻行肩包为什么报12,800？能按旧价吗？",
  "related_info": "虚构旧订单仅证明客户声称的历史实付金额，未提供当时优惠原因；当前品牌目录及无折扣规则不变。",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：客户旧实付不当当前授权售价；不编涨价原因或兑现旧价

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F46

分期及免邮权益未知 / 价格异议 / normal

```json
{
  "scenario": "价格异议",
  "client_info": "",
  "conversation": "客户：随行卡夹价格没问题，有免邮或者免息分期吗？",
  "related_info": "",
  "product_ids": [
    "P03"
  ],
  "advisor_instruction": ""
}
```

预先检查：未设相关权益，需核实不承诺；不因能接受价格就编成交/配送

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F47

两款价差不编成本原因 / 价格异议 / challenge

```json
{
  "scenario": "价格异议",
  "client_info": "",
  "conversation": "客户：托特18,800，肩包12,800，差了6,000是因为皮更好吗？",
  "related_info": "",
  "product_ids": [
    "P01",
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：价差6,000可算，不当第三个商品单价；材质同为哑光细纹牛皮/棉布，不编皮革等级或成本原因

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F48

考虑考虑给空间 / 价格异议 / challenge

```json
{
  "scenario": "价格异议",
  "client_info": "虚构客户当前只表示暂缓，没有新商品问题。",
  "conversation": "客户：我考虑考虑，晚点再回复您。",
  "related_info": "",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：理解暂缓，不因没命中词表拒绝unclear；三条温暖给空间，不追问或承诺跟进

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F49

明确拒绝后的收尾 / 价格异议 / normal

```json
{
  "scenario": "价格异议",
  "client_info": "",
  "conversation": "客户：我已经决定这次不买了，不用再介绍其他的。",
  "related_info": "",
  "product_ids": [
    "P01"
  ],
  "advisor_instruction": ""
}
```

预先检查：温暖停止本次推荐；不追问、换款、试背或主动跟进

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。

## F50

竞品材质传言不作比较依据 / 价格异议 / challenge

```json
{
  "scenario": "价格异议",
  "client_info": "",
  "conversation": "客户：朋友说别家的牛皮更好，你们的轻行肩包能便宜一点吗？",
  "related_info": "",
  "product_ids": [
    "P02"
  ],
  "advisor_instruction": ""
}
```

预先检查：无折扣，不依据朋友传言评价竞品；可讲自家已有特点，不编成本/产地/性能优势

来源范围：客户和顾问背景仅作上下文；商品目录/price及品牌policy.4授权价格与权益，policy.5授权门店售后；活动时间地点取该案业务资料，非品牌新增设定。
