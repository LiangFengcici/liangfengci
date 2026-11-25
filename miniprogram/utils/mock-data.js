/**
 * 离线演示数据（由 web/export_mock.py 从真实数据库导出，勿手改）。
 * 用途：真机/体验版在接口不可达时自动降级渲染，保证完整可看的界面。
 */
module.exports = {
  "catalog": [
    {
      "category_id": 1,
      "name": "口腔检查",
      "intro": "初诊检查、影像检查",
      "items": [
        {
          "catalog_id": 1,
          "category_id": 1,
          "name": "初诊口腔检查",
          "intro": "含口腔全面检查、治疗计划制定",
          "price_cents": 8000,
          "duration_slots": 1,
          "requires_consent": 0
        },
        {
          "catalog_id": 2,
          "category_id": 1,
          "name": "口腔全景片",
          "intro": "数字全景 X 光片",
          "price_cents": 12000,
          "duration_slots": 1,
          "requires_consent": 0
        }
      ]
    },
    {
      "category_id": 2,
      "name": "洁治",
      "intro": "超声波洁治与牙周维护",
      "items": [
        {
          "catalog_id": 3,
          "category_id": 2,
          "name": "超声波洁治",
          "intro": "全口超声洁治＋抛光",
          "price_cents": 28000,
          "duration_slots": 1,
          "requires_consent": 0
        },
        {
          "catalog_id": 4,
          "category_id": 2,
          "name": "龈下刮治（单象限）",
          "intro": "牙周基础治疗",
          "price_cents": 40000,
          "duration_slots": 1,
          "requires_consent": 0
        }
      ]
    },
    {
      "category_id": 3,
      "name": "补牙",
      "intro": "树脂充填与玻璃离子充填",
      "items": [
        {
          "catalog_id": 5,
          "category_id": 3,
          "name": "树脂充填（单面）",
          "intro": "进口纳米树脂，色泽匹配",
          "price_cents": 38000,
          "duration_slots": 1,
          "requires_consent": 0
        },
        {
          "catalog_id": 6,
          "category_id": 3,
          "name": "玻璃离子充填",
          "intro": "适用于乳牙与颈部缺损",
          "price_cents": 22000,
          "duration_slots": 1,
          "requires_consent": 0
        }
      ]
    },
    {
      "category_id": 4,
      "name": "根管治疗",
      "intro": "显微根管治疗",
      "items": [
        {
          "catalog_id": 7,
          "category_id": 4,
          "name": "根管治疗（前牙）",
          "intro": "显微根管，含充填",
          "price_cents": 90000,
          "duration_slots": 2,
          "requires_consent": 1
        },
        {
          "catalog_id": 8,
          "category_id": 4,
          "name": "根管治疗（磨牙）",
          "intro": "三根管以上，含热牙胶充填",
          "price_cents": 150000,
          "duration_slots": 2,
          "requires_consent": 1
        }
      ]
    },
    {
      "category_id": 5,
      "name": "修复",
      "intro": "全瓷冠、贴面与拔牙",
      "items": [
        {
          "catalog_id": 9,
          "category_id": 5,
          "name": "全瓷冠修复",
          "intro": "二氧化锆全瓷冠",
          "price_cents": 280000,
          "duration_slots": 2,
          "requires_consent": 0
        },
        {
          "catalog_id": 10,
          "category_id": 5,
          "name": "瓷贴面",
          "intro": "超薄美学贴面",
          "price_cents": 320000,
          "duration_slots": 2,
          "requires_consent": 0
        },
        {
          "catalog_id": 11,
          "category_id": 5,
          "name": "拔牙（简单）",
          "intro": "含局部麻醉",
          "price_cents": 30000,
          "duration_slots": 1,
          "requires_consent": 1
        },
        {
          "catalog_id": 12,
          "category_id": 5,
          "name": "拔牙（阻生智齿）",
          "intro": "微创拔除，含缝合",
          "price_cents": 120000,
          "duration_slots": 2,
          "requires_consent": 1
        }
      ]
    },
    {
      "category_id": 6,
      "name": "种植",
      "intro": "种植体植入与种植冠修复",
      "items": [
        {
          "catalog_id": 13,
          "category_id": 6,
          "name": "种植体植入",
          "intro": "含种植体与基台",
          "price_cents": 980000,
          "duration_slots": 3,
          "requires_consent": 1
        },
        {
          "catalog_id": 14,
          "category_id": 6,
          "name": "种植冠修复",
          "intro": "种植上部结构修复",
          "price_cents": 360000,
          "duration_slots": 2,
          "requires_consent": 0
        }
      ]
    },
    {
      "category_id": 7,
      "name": "正畸",
      "intro": "固定矫正与隐形矫正",
      "items": [
        {
          "catalog_id": 15,
          "category_id": 7,
          "name": "正畸初戴（金属自锁）",
          "intro": "全口托槽粘接与弓丝初戴",
          "price_cents": 880000,
          "duration_slots": 2,
          "requires_consent": 1
        },
        {
          "catalog_id": 16,
          "category_id": 7,
          "name": "正畸复诊加力",
          "intro": "更换弓丝与加力调整",
          "price_cents": 30000,
          "duration_slots": 1,
          "requires_consent": 0
        }
      ]
    },
    {
      "category_id": 8,
      "name": "儿童牙科",
      "intro": "窝沟封闭、涂氟与儿童充填",
      "items": [
        {
          "catalog_id": 17,
          "category_id": 8,
          "name": "窝沟封闭",
          "intro": "六龄齿防龋",
          "price_cents": 20000,
          "duration_slots": 1,
          "requires_consent": 0
        },
        {
          "catalog_id": 18,
          "category_id": 8,
          "name": "全口涂氟",
          "intro": "儿童防龋涂氟",
          "price_cents": 18000,
          "duration_slots": 1,
          "requires_consent": 0
        }
      ]
    }
  ],
  "clinics": [
    {
      "clinic_id": 1,
      "name": "中山路旗舰诊所",
      "address": "中山路 88 号 3 层"
    },
    {
      "clinic_id": 2,
      "name": "高新园区诊所",
      "address": "高新园区软件园 12 号楼 2 层"
    }
  ],
  "dentists": [
    {
      "dentist_id": 1,
      "name": "张明远",
      "title": "主任医师",
      "intro": "擅长种植与复杂根管，口腔种植资质 12 年",
      "quals": [
        "口腔执业医师",
        "口腔种植资质",
        "口腔颌面外科"
      ],
      "clinic": "中山路旗舰诊所"
    },
    {
      "dentist_id": 2,
      "name": "李慧",
      "title": "副主任医师",
      "intro": "正畸专科医师，隐适美认证",
      "quals": [
        "口腔执业医师",
        "正畸专科资质"
      ],
      "clinic": "高新园区诊所"
    },
    {
      "dentist_id": 3,
      "name": "王振宇",
      "title": "主治医师",
      "intro": "显微根管与美学充填",
      "quals": [
        "口腔执业医师"
      ],
      "clinic": "中山路旗舰诊所"
    },
    {
      "dentist_id": 4,
      "name": "陈雪",
      "title": "主治医师",
      "intro": "全瓷修复与贴面美学",
      "quals": [
        "口腔执业医师",
        "修复工艺资质"
      ],
      "clinic": "高新园区诊所"
    },
    {
      "dentist_id": 5,
      "name": "刘博",
      "title": "医师",
      "intro": "儿童牙科与预防保健",
      "quals": [
        "口腔执业医师"
      ],
      "clinic": "中山路旗舰诊所"
    }
  ]
}
