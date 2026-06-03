import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 读取 Key
api_key = os.getenv("DASHSCOPE_API_KEY")
print(f"正在尝试使用 Key: {api_key[:5]}****")

client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

try:
    # 尝试调用模型
    response = client.chat.completions.create(
        model="qwen3.7-max",
        messages=[{"role": "user", "content": "请回答：连通性测试成功"}]
    )
    print("【恭喜！】API Key 验证成功，模型响应为：")
    print(response.choices[0].message.content)
except Exception as e:
    print("【警告！】API 调用失败，请检查错误详情：")
    print(e)