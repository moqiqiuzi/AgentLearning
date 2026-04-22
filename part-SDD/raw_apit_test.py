"""
裸 API 调用测试 
体验「无状态推理」：模型不知道项目背景，不能读写文件
"""
import os
import json
import urllib.request

# 智谱 CodingPlan 专用接口
API_KEY = "/"
API_URL = "https://open.bigmodel.cn/api/paas/v3/model-api/chatglm_lite/sse-invoke"

def call_api(prompt: str) -> str:
    data = json.dumps({
        "prompt": prompt,
        "temperature": 0.1,
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode()
    except Exception as e:
        return f"请求失败：{str(e)}"

if __name__ == "__main__":
    print("=" * 60)
    print("测试：裸 API 无状态推理演示")
    print("=" * 60)

    response = call_api("你好，请介绍一下你自己")
    print(response)

    print("\n" * 2)
    print("=" * 60)
