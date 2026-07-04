import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

import pytest
from backend.intent_router import detect_intent_and_params
from tools.registry import tool_registry

def test_intent_router_communication_detection():
    # 1. Wait pattern
    res = detect_intent_and_params("please wait 5 seconds")
    assert res["intent"] == "wait"
    assert res["parameters"]["seconds"] == 5

    # 2. Email patterns
    res = detect_intent_and_params("send email to test@domain.com saying hello team")
    assert res["intent"] == "send_email"
    assert res["parameters"]["to"] == "test@domain.com"
    assert res["parameters"]["body"] == "hello team"

    res = detect_intent_and_params("read my inbox")
    assert res["intent"] == "read_email"

    # 3. Discord patterns
    res = detect_intent_and_params("send discord message to #development saying server is online")
    assert res["intent"] == "send_discord"
    assert res["parameters"]["channel"] == "development"
    assert res["parameters"]["message"] == "server is online"

    res = detect_intent_and_params("read discord channel #development")
    assert res["intent"] == "read_discord"
    assert res["parameters"]["channel"] == "development"

    # 4. Telegram patterns
    res = detect_intent_and_params("send telegram message to mom saying i had lunch")
    assert res["intent"] == "send_telegram"
    assert res["parameters"]["contact"] == "mom"
    assert res["parameters"]["message"] == "i had lunch"

    res = detect_intent_and_params("read telegram chats from sam_partner")
    assert res["intent"] == "read_telegram"
    assert res["parameters"]["contact"] == "sam_partner"

    # 5. Slack patterns
    res = detect_intent_and_params("send slack message to general saying good morning team")
    assert res["intent"] == "send_slack"
    assert res["parameters"]["channel"] == "general"
    assert res["parameters"]["message"] == "good morning team"

    res = detect_intent_and_params("read slack messages for general")
    assert res["intent"] == "read_slack"
    assert res["parameters"]["channel"] == "general"

def test_communication_tool_execution():
    # Email
    assert "send_email" in tool_registry.tools
    assert "read_email" in tool_registry.tools
    
    send_email_func = tool_registry.get_tool("send_email")
    res_send = send_email_func(to="investor@vc.com", body="Meeting at 2PM")
    assert res_send["status"] == "ok"
    assert "investor@vc.com" in res_send["message"]

    read_email_func = tool_registry.get_tool("read_email")
    res_read = read_email_func(sender="John Smith")
    assert res_read["status"] == "ok"
    assert len(res_read["data"]) > 0

    # Discord
    assert "send_discord" in tool_registry.tools
    assert "read_discord" in tool_registry.tools

    send_disc_func = tool_registry.get_tool("send_discord")
    res_disc_send = send_disc_func(channel="development", message="Hello world")
    assert res_disc_send["status"] == "ok"

    read_disc_func = tool_registry.get_tool("read_discord")
    res_disc_read = read_disc_func(channel="development")
    assert res_disc_read["status"] == "ok"
    assert any(m["content"] == "Hello world" for m in res_disc_read["data"])

    # Telegram
    assert "send_telegram" in tool_registry.tools
    assert "read_telegram" in tool_registry.tools

    send_tg_func = tool_registry.get_tool("send_telegram")
    res_tg_send = send_tg_func(contact="mom", message="On my way")
    assert res_tg_send["status"] == "ok"

    read_tg_func = tool_registry.get_tool("read_telegram")
    res_tg_read = read_tg_func(contact="mom")
    assert res_tg_read["status"] == "ok"
    assert any(m["content"] == "On my way" for m in res_tg_read["data"])

    # Slack
    assert "send_slack" in tool_registry.tools
    assert "read_slack" in tool_registry.tools

    send_slack_func = tool_registry.get_tool("send_slack")
    res_slack_send = send_slack_func(channel="general", message="Slack alert")
    assert res_slack_send["status"] == "ok"

    read_slack_func = tool_registry.get_tool("read_slack")
    res_slack_read = read_slack_func(channel="general")
    assert res_slack_read["status"] == "ok"
    assert any(m["content"] == "Slack alert" for m in res_slack_read["data"])

    # Wait
    assert "wait" in tool_registry.tools
    wait_func = tool_registry.get_tool("wait")
    res_wait = wait_func(seconds=1)
    assert res_wait["status"] == "ok"
