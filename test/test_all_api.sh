#!/bin/bash
# ============================================================
# Jabobo Backend API 全量测试脚本
# 用法: bash test/test_all_api.sh
# ============================================================

set -e

# -------------------- 配置区 --------------------
BASE_URL="http://localhost:8007/api"
USERNAME="testuser"
PASSWORD="testpass123"
ADMIN_USER="admin"
ADMIN_PASS="admin123"
JABOBO_ID="AA:BB:CC:DD:EE:FF"
NEW_JABOBO_ID="11:22:33:44:55:66"
TEST_FILE_PATH="/tmp/test_kb.txt"
NEW_USER="apitest_user_$(date +%s)"
NEW_PASS="TestPass123!"

# -------------------- 颜色 --------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# -------------------- 工具函数 --------------------
print_header() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
}

print_test() {
    echo -e "\n${YELLOW}▶ $1${NC}"
    echo -e "  ${YELLOW}curl $2${NC}"
}

result_ok() {
    echo -e "  ${GREEN}✓ PASS${NC} — $1"
    ((PASS_COUNT++))
}

result_fail() {
    echo -e "  ${RED}✗ FAIL${NC} — $1"
    ((FAIL_COUNT++))
}

result_skip() {
    echo -e "  ${YELLOW}⊘ SKIP${NC} — $1"
    ((SKIP_COUNT++))
}

# 封装 curl 请求，自动判断成功/失败
run_test() {
    local desc="$1"
    local method="$2"
    local url="$3"
    shift 3
    # 剩余参数直接传给 curl
    print_test "$desc" "$method $url"

    HTTP_CODE=$(curl -s -w "%{http_code}" -o /tmp/api_response.json "$@" -X "$method" "$url")

    BODY=$(cat /tmp/api_response.json 2>/dev/null || echo "")

    if echo "$HTTP_CODE" | grep -qE "^[23]"; then
        result_ok "HTTP $HTTP_CODE"
        echo "  Response: $(echo "$BODY" | head -c 300)"
    else
        result_fail "HTTP $HTTP_CODE"
        echo "  Response: $(echo "$BODY" | head -c 300)"
    fi
}

# -------------------- 预检查 --------------------
echo -e "${CYAN}预检查: 测试服务器连通性...${NC}"
if ! curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/config/server-base" | grep -qE "^[23]"; then
    echo -e "${RED}错误: 无法连接 $BASE_URL，请确保服务已启动${NC}"
    echo -e "  启动命令: ${YELLOW}uvicorn app.main:app --host 0.0.0.0 --port 8007 --reload${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 服务器连通${NC}\n"

# 创建临时测试文件
echo "这是一个知识库测试文件。" > "$TEST_FILE_PATH"

# ============================================================
# 1. 认证模块
# ============================================================
print_header "1. 认证模块 (Auth)"

# 1.1 登录
run_test "用户登录" POST "$BASE_URL/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"$USERNAME\", \"password\": \"$PASSWORD\", \"client_type\": \"web\"}"

# 提取 token
TOKEN=$(python3 -c "import json; d=json.load(open('/tmp/api_response.json')); print(d.get('token',''))" 2>/dev/null || echo "")
if [ -z "$TOKEN" ]; then
    echo -e "  ${RED}无法提取 token，后续认证接口将失败${NC}"
else
    echo -e "  ${GREEN}Token: ${TOKEN:0:20}...${NC}"
fi

# 1.2 管理员登录
run_test "管理员登录" POST "$BASE_URL/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"$ADMIN_USER\", \"password\": \"$ADMIN_PASS\", \"client_type\": \"web\"}"

ADMIN_TOKEN=$(python3 -c "import json; d=json.load(open('/tmp/api_response.json')); print(d.get('token',''))" 2>/dev/null || echo "")

# ============================================================
# 2. 用户管理模块
# ============================================================
print_header "2. 用户管理模块 (Users)"

# 2.1 获取用户列表
if [ -n "$ADMIN_TOKEN" ]; then
    run_test "获取用户列表" GET "$BASE_URL/users" \
        -H "x-username: $ADMIN_USER" \
        -H "Authorization: Bearer $ADMIN_TOKEN"
else
    result_skip "获取用户列表 — 无 admin token"
fi

# 2.2 创建用户
if [ -n "$ADMIN_TOKEN" ]; then
    run_test "创建新用户" POST "$BASE_URL/users" \
        -H "x-username: $ADMIN_USER" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$NEW_USER\", \"password\": \"$NEW_PASS\", \"role\": \"User\"}"
else
    result_skip "创建新用户 — 无 admin token"
fi

# 2.3 修改密码
if [ -n "$TOKEN" ]; then
    run_test "修改密码" PUT "$BASE_URL/users/password" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$USERNAME\", \"new_password\": \"$PASSWORD\"}"
else
    result_skip "修改密码 — 无 token"
fi

# 2.4 删除刚创建的用户
if [ -n "$ADMIN_TOKEN" ]; then
    run_test "删除用户 $NEW_USER" POST "$BASE_URL/users/$NEW_USER" \
        -H "x-username: $ADMIN_USER" \
        -H "Authorization: Bearer $ADMIN_TOKEN"
else
    result_skip "删除用户 — 无 admin token"
fi

# ============================================================
# 3. 设备绑定模块
# ============================================================
print_header "3. 设备绑定模块 (Jabobo Manager)"

# 3.1 绑定设备
if [ -n "$TOKEN" ]; then
    run_test "绑定设备" POST "$BASE_URL/user/bind" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"jabobo_id\": \"$JABOBO_ID\"}"
else
    result_skip "绑定设备 — 无 token"
fi

# 3.2 获取设备列表
if [ -n "$TOKEN" ]; then
    run_test "获取已绑定设备列表" GET "$BASE_URL/user/jabobo_ids" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN"
else
    result_skip "获取设备列表 — 无 token"
fi

# 3.3 重绑定设备
if [ -n "$TOKEN" ]; then
    run_test "重绑定设备" PUT "$BASE_URL/user/rebind" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"old_jabobo_id\": \"$JABOBO_ID\", \"new_jabobo_id\": \"$NEW_JABOBO_ID\"}"
else
    result_skip "重绑定设备 — 无 token"
fi

# 3.4 解绑设备（清理）
if [ -n "$TOKEN" ]; then
    run_test "解绑设备 $NEW_JABOBO_ID" DELETE "$BASE_URL/user/unbind?jabobo_id=$NEW_JABOBO_ID" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN"
else
    result_skip "解绑设备 — 无 token"
fi

# ============================================================
# 4. 设备配置模块
# ============================================================
print_header "4. 设备配置模块 (Jabobo Config)"

# 先绑定设备用于后续测试
if [ -n "$TOKEN" ]; then
    curl -s -X POST "$BASE_URL/user/bind" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"jabobo_id\": \"$JABOBO_ID\"}" > /dev/null 2>&1
fi

# 4.1 获取设备配置
if [ -n "$TOKEN" ]; then
    run_test "获取设备配置" GET "$BASE_URL/user/config?jabobo_id=$JABOBO_ID" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN"
else
    result_skip "获取设备配置 — 无 token"
fi

# 4.2 同步配置
if [ -n "$TOKEN" ]; then
    run_test "同步设备配置 (persona + memory)" POST "$BASE_URL/user/sync-config" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"jabobo_id\": \"$JABOBO_ID\", \"persona\": \"{\\\"name\\\": \\\"小助手\\\", \\\"style\\\": \\\"友好\\\"}\", \"memory\": \"用户喜欢听音乐\"}"
else
    result_skip "同步配置 — 无 token"
fi

# ============================================================
# 5. 服务配置模块（设备端）
# ============================================================
print_header "5. 服务配置模块 (Config — 设备端)"

run_test "获取服务器基础配置" POST "$BASE_URL/config/server-base"

run_test "获取 Agent 模型配置" POST "$BASE_URL/config/agent-models" \
    -H "Content-Type: application/json" \
    -d "{\"macAddress\": \"$JABOBO_ID\", \"clientId\": \"test-client\"}"

run_test "保存 Agent 记忆" PUT "$BASE_URL/agent/saveMemory/$JABOBO_ID" \
    -H "Content-Type: application/json" \
    -d "{\"summaryMemory\": \"这是一段测试对话摘要\"}"

# ============================================================
# 6. 知识库模块
# ============================================================
print_header "6. 知识库模块 (Knowledge Base)"

# 6.1 上传文件
if [ -n "$TOKEN" ]; then
    run_test "上传知识库文件" POST "$BASE_URL/user/upload-kb" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN" \
        -F "jabobo_id=$JABOBO_ID" \
        -F "file=@$TEST_FILE_PATH"
else
    result_skip "上传知识库文件 — 无 token"
fi

# 6.2 列出知识库
if [ -n "$TOKEN" ]; then
    run_test "列出知识库文件" GET "$BASE_URL/user/list-kb?jabobo_id=$JABOBO_ID" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN"
else
    result_skip "列出知识库文件 — 无 token"
fi

# 6.3 生成 RAG 提示词
run_test "生成 RAG 提示词" POST "$BASE_URL/user/generate-rag-prompt" \
    -H "Content-Type: application/json" \
    -d "{\"jabobo_id\": \"$JABOBO_ID\", \"question\": \"Jabobo怎么连接WiFi？\"}"

# 6.4 删除知识库文件（需要实际路径）
if [ -n "$TOKEN" ]; then
    result_skip "删除知识库文件 — 需要实际 file_path"
else
    result_skip "删除知识库文件 — 无 token"
fi

# ============================================================
# 7. 语音模块
# ============================================================
print_header "7. 语音模块 (Voice)"

# 7.1 上报聊天记录
run_test "上报聊天记录" POST "$BASE_URL/agent/chat-history/report" \
    -H "Content-Type: application/json" \
    -d "{\"macAddress\": \"$JABOBO_ID\", \"sessionId\": \"session-$(date +%s)\", \"chatType\": \"voice\", \"content\": \"你好，今天天气怎么样？\", \"reportTime\": $(date +%s)}"

# 7.2 获取音频列表
if [ -n "$TOKEN" ]; then
    run_test "获取音频列表" GET "$BASE_URL/user/list-audio?jabobo_id=$JABOBO_ID" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN"
else
    result_skip "获取音频列表 — 无 token"
fi

# 7.3 声纹列表
if [ -n "$TOKEN" ]; then
    run_test "获取声纹列表" GET "$BASE_URL/voiceprint/list?jabobo_id=$JABOBO_ID" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN"
else
    result_skip "获取声纹列表 — 无 token"
fi

# 7.4 上传音频 / 注册声纹 / 删除声纹 需要实际文件
result_skip "上传音频文件 — 需要实际音频文件"
result_skip "注册声纹 — 需要实际 WAV 文件"
result_skip "删除声纹 — 需要先注册声纹"

# ============================================================
# 8. 设备数据 & OTA
# ============================================================
print_header "8. 设备数据 & OTA 模块"

run_test "获取设备完整数据" GET "$BASE_URL/user/device/full_data?jabobo_id=$JABOBO_ID"

run_test "更新设备版本" PUT "$BASE_URL/user/device/update_version?jabobo_id=$JABOBO_ID&current_version=1.0.0&expected_version=2.0.0"

run_test "OTA 检查更新" POST "$BASE_URL/user/device/ota" \
    -H "Device-Id: $JABOBO_ID" \
    -H "Content-Type: application/json" \
    -d "{\"mac_address\": \"$JABOBO_ID\"}"

run_test "OTA 激活" POST "$BASE_URL/user/device/ota/activate" \
    -H "Device-Id: $JABOBO_ID" \
    -H "Content-Type: application/json" \
    -d "{\"mac_address\": \"$JABOBO_ID\"}"

run_test "检查固件文件 (HEAD)" "HEAD" "$BASE_URL/xiaozhi/otaMag/download/Jabobo.bin"

# ============================================================
# 9. App 管理模块
# ============================================================
print_header "9. App 管理模块"

run_test "获取最新版本 (Android)" GET "$BASE_URL/app/latest-version?platform=android"

run_test "获取最新版本 (iOS)" GET "$BASE_URL/app/latest-version?platform=ios"

run_test "获取 iOS plist" GET "$BASE_URL/app/ios-plist"

# ============================================================
# 10. 登出模块
# ============================================================
print_header "10. 登出 (Logout)"

if [ -n "$TOKEN" ]; then
    run_test "登出当前设备" POST "$BASE_URL/logout" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN"
else
    result_skip "登出 — 无 token"
fi

# 重新登录测试 logout/all
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"$USERNAME\", \"password\": \"$PASSWORD\", \"client_type\": \"android\"}")
TOKEN2=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")

if [ -n "$TOKEN2" ]; then
    run_test "登出所有设备" POST "$BASE_URL/logout/all" \
        -H "x-username: $USERNAME" \
        -H "Authorization: Bearer $TOKEN2"
else
    result_skip "登出所有设备 — 重新登录失败"
fi

# -------------------- 清理 --------------------
rm -f "$TEST_FILE_PATH" /tmp/api_response.json

# -------------------- 测试报告 --------------------
TOTAL=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  测试报告${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}通过: $PASS_COUNT${NC}"
echo -e "  ${RED}失败: $FAIL_COUNT${NC}"
echo -e "  ${YELLOW}跳过: $SKIP_COUNT${NC}"
echo -e "  总计: $TOTAL"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "${RED}存在失败的测试，请检查上方输出。${NC}"
    exit 1
else
    echo -e "${GREEN}所有测试通过！${NC}"
    exit 0
fi
