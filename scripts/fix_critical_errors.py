# fix_remaining_errors.py
import os
import re


def fix_file(filepath, replacements):
    """رفع خطاهای یک فایل"""
    if not os.path.exists(filepath):
        print(f"⚠️ File not found: {filepath}")
        return False

    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    changed = False
    for search, replace in replacements:
        new_content = re.sub(search, replace, content, flags=re.MULTILINE)
        if new_content != content:
            content = new_content
            changed = True

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Fixed: {filepath}")
        return True
    return False

def main():
    print("="*70)
    print("🔧 FIXING REMAINING 11 ERRORS")
    print("="*70)

    fixes = [
        # 1. test_5000_questions.py - F821: undefined name 'score'
        {
            'file': 'tests/test_5000_questions.py',
            'replacements': [
                (r'Q\(cat, f"A{\d+\+i\+1}: .*? score = \(',
                 r'Q(cat, f"A{num+i+1}: ... score = {score}")'),
                (r'Q\(cat, f"A{\d+\+i\+1}: confidence = \(',
                 r'Q(cat, f"A{num+i+1}: confidence = {confidence}")'),
            ]
        },

        # 2. test_screener_flow.py - E999: unmatched ')'
        {
            'file': 'tests/test_screener_flow.py',
            'replacements': [
                (r"'total'\)\}\"", r"'total')}\""),
                (r'print\(f"  Screened \{len\(results\)\} symbols, total = \(',
                 r'print(f"  Screened {len(results)} symbols, total = {total}")'),
            ]
        },

        # 3-6. backtesting files - class definitions
        {
            'file': 'tests/unit/backtesting/test_auction_engine.py',
            'replacements': [
                (r'TestAuctionEngine: pass', r'class TestAuctionEngine:\n    pass'),
                (r'TestAuctionEngine:,\s*$', r'class TestAuctionEngine:\n    pass'),
            ]
        },
        {
            'file': 'tests/unit/backtesting/test_live_data_adapter.py',
            'replacements': [
                (r'TestLiveDataAdapter: pass', r'class TestLiveDataAdapter:\n    pass'),
                (r'TestLiveDataAdapter:,\s*$', r'class TestLiveDataAdapter:\n    pass'),
            ]
        },
        {
            'file': 'tests/unit/backtesting/test_memory_manager.py',
            'replacements': [
                (r'TestMemoryManager: pass', r'class TestMemoryManager:\n    pass'),
                (r'TestMemoryManager:,\s*$', r'class TestMemoryManager:\n    pass'),
            ]
        },
        {
            'file': 'tests/unit/backtesting/test_rebalancer.py',
            'replacements': [
                (r'TestRebalancer: pass', r'class TestRebalancer:\n    pass'),
                (r'TestRebalancer:,\s*$', r'class TestRebalancer:\n    pass'),
            ]
        },
        {
            'file': 'tests/unit/backtesting/test_simulation_logger.py',
            'replacements': [
                (r'TestSimulationLogger: pass', r'class TestSimulationLogger:\n    pass'),
                (r'TestSimulationLogger:,\s*$', r'class TestSimulationLogger:\n    pass'),
            ]
        },

        # 7. test_audit_modules.py - E999: unmatched '}'
        {
            'file': 'tests/unit/services/test_audit_modules.py',
            'replacements': [
                (r'i \+ 1\)\} for i in range\(50', r'i + 1} for i in range(50)'),
                (r'items = \(\s*i \+ 1\)\} for i in range\(50',
                 r'items = {i + 1 for i in range(50)}'),
            ]
        },

        # 8. test_orchestrator_signal_integration.py - E999: unmatched ')'
        {
            'file': 'tests/unit/services/test_orchestrator_signal_integration.py',
            'replacements': [
                (r'^     \)$', r'    )'),
                (r'\)\s*$', r')'),
            ]
        },

        # 9. test_cron_alerts.py - E999: IndentationError
        {
            'file': 'tests/unit/test_cron_alerts.py',
            'replacements': [
                (r'        assert app_mod\._alert_state\["consecutive_failures"\] > 0',
                 r'    assert app_mod._alert_state["consecutive_failures"] > 0'),
                (r'        assert app_mod\._alert_state\["was_in_failure_streak"\] > 0',
                 r'    assert app_mod._alert_state["was_in_failure_streak"] > 0'),
            ]
        },

        # 10. test_backtest_api_integration.py - fix indent
        {
            'file': 'tests/test_backtest_api_integration.py',
            'replacements': [
                (r'        assert isinstance\(items, list\)', r'    assert isinstance(items, list)'),
            ]
        },

        # 11. test_all_modules.py - f-string with backslash
        {
            'file': 'tests/test_all_modules.py',
            'replacements': [
                (r'print\(f"  Ensemble: \{result\[\'test\'\]\[\'action\'\]\} conf = \(',
                 r'print(f"  Ensemble: {result[\'test\'][\'action\']} conf = {confidence}")'),
            ]
        },
    ]

    for fix in fixes:
        fix_file(fix['file'], fix['replacements'])

    print("\n" + "="*70)
    print("✅ DONE!")
    print("\n📋 Now run:")
    print("   black tests/ --line-length 120")
    print("   flake8 tests/ --select=E9,F821 --statistics")
    print("   pytest tests/ -v --tb=short")
    print("="*70)

if __name__ == "__main__":
    main()
