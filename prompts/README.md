# Prompt 编写指南

本项目采用 **三层 Prompt 体系**，你可以根据需要扩展自定义 Prompt。

## 目录结构

```
prompts/
├── system/           # 系统默认 Prompt
│   └── default_zh.md
├── apps/             # App 专用 Prompt  
│   ├── wechat.yaml
│   └── taobao.yaml
└── features/         # 功能描述词
    ├── compare_price.yaml
    └── search.yaml
```

---

## 1. App 专用 Prompt

当检测到用户正在操作特定 App 时，自动加载对应的操作指南。

### 文件格式

```yaml
# prompts/apps/{app_name}.yaml

name: 应用名称           # 显示名称
package: com.xxx.xxx    # 包名（用于匹配当前应用）
aliases:                # 别名列表
  - 别名1
  - 别名2

system_prompt: |
  ## 应用界面结构
  
  ### 主界面
  - 描述主要 UI 布局
  - 描述底部 Tab 结构
  
  ### 常用操作
  
  #### 操作名称
  1. 步骤一
  2. 步骤二
  
  ### 注意事项
  - 特殊注意点

# 可选：场景化提示
scenarios:
  场景名称:
    trigger: "触发关键词1|关键词2"
    prompt: |
      场景专用提示...
```

### 示例

```yaml
# prompts/apps/jd.yaml
name: 京东
package: com.jingdong.app.mall
aliases:
  - JD
  - 京东商城

system_prompt: |
  ## 京东界面结构
  
  ### 主界面
  - 顶部搜索框可直接搜索商品
  - 底部 Tab：首页、分类、购物车、我的
  
  ### 常用操作
  
  #### 搜索商品
  1. 点击顶部搜索框
  2. 输入商品名称
  3. 点击搜索
```

---

## 2. 功能描述词

当检测到用户任务中包含特定功能关键词时，自动加载专业指导。

### 文件格式

```yaml
# prompts/features/{feature_name}.yaml

name: 功能名称
trigger_keywords:       # 触发关键词列表
  - 关键词1
  - 关键词2

system_prompt: |
  ## 功能任务指南
  
  ### 策略
  1. 步骤描述
  
  ### 注意事项
  - 注意点

examples:               # 可选：示例任务
  - "示例任务描述1"
  - "示例任务描述2"
```

### 示例

```yaml
# prompts/features/order_food.yaml
name: 外卖点餐
trigger_keywords:
  - 点外卖
  - 叫外卖
  - 订餐
  - 点餐

system_prompt: |
  ## 外卖点餐指南
  
  ### 点餐策略
  1. 打开外卖 App（美团/饿了么）
  2. 确认收货地址
  3. 搜索或浏览餐厅
  4. 选择菜品加入购物车
  5. 确认订单并支付
  
  ### 注意事项
  - 确认配送时间
  - 检查优惠券
  - 备注口味要求

examples:
  - "帮我在美团点一份麻辣烫"
  - "在饿了么搜索附近的奶茶店"
```

---

## 3. 编写技巧

### ✅ 推荐

- **具体步骤**：分步骤描述操作流程
- **UI 描述**：描述界面布局帮助模型定位
- **常见包名**：提供完整包名方便直接启动

### ❌ 避免

- 过于笼统的描述
- 假设模型了解最新 UI（应用更新会变化）
- 过长的单段文字

---

## 4. 测试你的 Prompt

```python
from phone_agent.prompts import PromptManager, PromptContext

manager = PromptManager("prompts")
manager.load()

# 检查 App Prompt 加载
print(manager.list_apps())

# 检查功能检测
feature = manager.detect_feature("帮我比价一下这个商品")
print(f"检测到功能: {feature}")

# 构建完整 Prompt
context = PromptContext(
    task="打开淘宝搜索蓝牙耳机",
    current_app="com.taobao.taobao",
)
prompt = manager.build_system_prompt(context)
print(prompt)
```
