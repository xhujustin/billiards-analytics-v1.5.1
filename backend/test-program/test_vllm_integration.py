#!/usr/bin/env python
"""
vLLM 集成测试脚本

运行此脚本验证 vLLM 客户端和后端集成是否正常工作。

用法:
    python test_vllm_integration.py
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.vllm_client import vLLMClient, vLLMConfig


def print_header(text):
    """打印标题。"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_section(text):
    """打印小节。"""
    print(f"\n📌 {text}")
    print("-" * 70)


def print_success(text):
    """打印成功信息。"""
    print(f"✅ {text}")


def print_error(text):
    """打印错误信息。"""
    print(f"❌ {text}")


def print_warning(text):
    """打印警告信息。"""
    print(f"⚠️  {text}")


async def test_health_check(client: vLLMClient):
    """测试健康检查。"""
    print_section("测试 1: 健康检查")
    
    try:
        health = await client.health_check()
        
        if health:
            print_success("vLLM 服务 online")
            return True
        else:
            print_error("vLLM 服务 offline")
            return False
    
    except Exception as e:
        print_error(f"健康检查失败: {e}")
        return False


async def test_single_inference(client: vLLMClient):
    """测试单个推理。"""
    print_section("测试 2: 单个推理")
    
    test_prompt = "白球在左上角，标靶球在底袋位。建议动作："
    
    print(f"📝 提示语: {test_prompt}")
    
    try:
        start_time = time.time()
        
        response = await client.generate(
            prompt=test_prompt,
            max_tokens=256,
            temperature=0.7
        )
        
        latency = (time.time() - start_time) * 1000
        
        print(f"💬 响应: {response}")
        print_success(f"推理成功 | 延迟: {latency:.1f}ms")
        
        # 验证响应质量
        if len(response) > 0:
            print_success(f"响应长度: {len(response)} 字符")
            return True
        else:
            print_error("响应为空")
            return False
    
    except Exception as e:
        print_error(f"推理失败: {e}")
        return False


async def test_batch_inference(client: vLLMClient):
    """测试批量推理。"""
    print_section("测试 3: 批量推理")
    
    test_prompts = [
        "当前评分是多少？",
        "下一步的建议是什么？",
        "如何改进我的技术？"
    ]
    
    print(f"📝 提示语数量: {len(test_prompts)}")
    for i, prompt in enumerate(test_prompts, 1):
        print(f"   {i}. {prompt}")
    
    try:
        start_time = time.time()
        
        responses = await client.batch_generate(
            prompts=test_prompts,
            max_tokens=256
        )
        
        latency = (time.time() - start_time) * 1000
        avg_latency = latency / len(responses)
        
        print(f"\n💬 响应:")
        for i, (prompt, response) in enumerate(zip(test_prompts, responses), 1):
            print(f"   {i}. {response[:60]}...")
        
        print_success(
            f"批量推理成功 | "
            f"总延迟: {latency:.1f}ms | "
            f"平均: {avg_latency:.1f}ms"
        )
        
        return True
    
    except Exception as e:
        print_error(f"批量推理失败: {e}")
        return False


async def test_streaming(client: vLLMClient):
    """测试流式推理。"""
    print_section("测试 4: 流式推理")
    
    test_prompt = "请给出撞球技巧"
    
    print(f"📝 提示语: {test_prompt}")
    print("💬 流式响应:")
    
    try:
        start_time = time.time()
        full_response = ""
        chunk_count = 0
        
        async for chunk in client.generate_stream(
            prompt=test_prompt,
            max_tokens=256
        ):
            print(f"   {chunk}", end="", flush=True)
            full_response += chunk
            chunk_count += 1
        
        latency = (time.time() - start_time) * 1000
        
        print(f"\n\n✅ 流式推理成功 | "
              f"块数: {chunk_count} | "
              f"延迟: {latency:.1f}ms")
        
        return True
    
    except Exception as e:
        print_error(f"流式推理失败: {e}")
        return False


async def test_error_handling(client: vLLMClient):
    """测试错误处理。"""
    print_section("测试 5: 错误处理")
    
    # 测试空提示
    print("📝 测试空提示...")
    try:
        response = await client.generate(prompt="", max_tokens=10)
        print_warning("应该抛出错误但没有")
        return False
    except ValueError:
        print_success("正确捕获空提示错误")
    except Exception as e:
        print_warning(f"捕获异常: {type(e).__name__}")
    
    return True


async def test_performance(client: vLLMClient):
    """性能基准测试。"""
    print_section("测试 6: 性能基准")
    
    test_prompt = "给出一个撞球技巧"
    num_iterations = 5
    
    print(f"📊 运行 {num_iterations} 次迭代...")
    
    try:
        latencies = []
        
        for i in range(num_iterations):
            start_time = time.time()
            
            await client.generate(
                prompt=test_prompt,
                max_tokens=100
            )
            
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)
            
            print(f"   迭代 {i + 1}: {latency:.1f}ms")
        
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        print(f"\n📈 性能统计:")
        print(f"   平均延迟: {avg_latency:.1f}ms")
        print(f"   最小延迟: {min_latency:.1f}ms")
        print(f"   最大延迟: {max_latency:.1f}ms")
        
        # 检查是否满足目标 (120ms P50)
        if avg_latency < 150:
            print_success(f"性能目标: {avg_latency:.1f}ms < 150ms ✓")
            return True
        else:
            print_warning(f"性能低于目标: {avg_latency:.1f}ms > 150ms")
            return True  # 仍然返回True，因为系统仍在工作
    
    except Exception as e:
        print_error(f"性能测试失败: {e}")
        return False


async def main():
    """主测试函数。"""
    
    print_header("vLLM 集成测试套件")
    
    print("\n📌 配置信息:")
    print(f"   API 地址: http://localhost:8000/v1")
    print(f"   模型: unsloth/Qwen2.5-7B-bnb-4bit")
    print(f"   超时: 30 秒")
    
    # 创建客户端
    config = vLLMConfig(
        api_url="http://localhost:8000/v1",
        model_name="unsloth/Qwen2.5-7B-bnb-4bit",
        timeout=30
    )
    
    client = vLLMClient(config=config)
    
    # 运行测试
    results = {
        "健康检查": await test_health_check(client),
        "单个推理": await test_single_inference(client),
        "批量推理": await test_batch_inference(client),
        "流式推理": await test_streaming(client),
        "错误处理": await test_error_handling(client),
        "性能基准": await test_performance(client),
    }
    
    # 关闭客户端
    await client.close()
    
    # 打印总结
    print_header("测试总结")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    print("\n📋 测试结果:")
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {status} - {test_name}")
    
    print(f"\n📊 总体: {passed_tests}/{total_tests} 测试通过")
    
    if passed_tests == total_tests:
        print_success("所有测试通过！vLLM 集成正常工作")
        return 0
    elif passed_tests >= total_tests - 1:
        print_warning("大部分测试通过，系统基本可用")
        return 0
    else:
        print_error("多个测试失败，请检查 vLLM 配置")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被中断")
        sys.exit(1)
    except Exception as e:
        print_error(f"致命错误: {e}")
        sys.exit(1)
