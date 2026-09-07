from pathlib import Path
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "Webaria" / "paper-engine.js"


def run_node(source: str) -> str:
    result = subprocess.run(
        ["node", "--input-type=commonjs", "-e", source],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def test_webaria_paper_engine_loads_and_validates_core_risk_rules():
    js = textwrap.dedent(
        f"""
        const fs = require('fs');
        const vm = require('vm');
        const source = fs.readFileSync({str(ENGINE)!r}, 'utf8');
        const context = {{ console }};
        vm.createContext(context);
        vm.runInContext(source, context);
        const E = context.WebariaPaperEngine;
        if (!E) throw new Error('engine export missing');
        const stops = E.validateStops('LONG', 101, 99, 105);
        if (stops.stop !== 99 || stops.target !== 105) throw new Error('LONG stop validation failed');
        const shortStops = E.validateStops('SHORT', 101, 103, 99);
        if (shortStops.stop !== 103 || shortStops.target !== 99) throw new Error('SHORT stop validation failed');
        const risk = E.positionSize(10000, 100, 99, 0.01, {{ quantityStep: 3 }});
        if (risk !== 99) throw new Error('quantity step must floor');
        const pnl = E.unrealizedPnl({{ side: 'SHORT', quantity: 10, entry: 100 }}, 98);
        if (pnl !== 20) throw new Error('pnl calculation failed');
        console.log('ok');
        """
    )
    assert run_node(js) == "ok"


def test_webaria_paper_engine_stop_has_conservative_priority():
    js = textwrap.dedent(
        f"""
        const fs = require('fs');
        const vm = require('vm');
        const source = fs.readFileSync({str(ENGINE)!r}, 'utf8');
        const context = {{ console }};
        vm.createContext(context);
        vm.runInContext(source, context);
        const E = context.WebariaPaperEngine;
        const result = E.barExit({{ side: 'LONG', sl: 99, tp: 103 }}, {{ high: 104, low: 98 }});
        if (!result || result.reason !== 'stop loss' || result.outcome !== 'LOSS') throw new Error('STOP-first rule failed');
        console.log('ok');
        """
    )
    assert run_node(js) == "ok"


def test_webaria_paper_engine_blocks_wrong_side_stops():
    js = textwrap.dedent(
        f"""
        const fs = require('fs');
        const vm = require('vm');
        const source = fs.readFileSync({str(ENGINE)!r}, 'utf8');
        const context = {{ console }};
        vm.createContext(context);
        vm.runInContext(source, context);
        const E = context.WebariaPaperEngine;
        let blocked = false;
        try {{ E.validateStops('SHORT', 100, 99, 95); }} catch (error) {{ blocked = /wrong side/.test(error.message); }}
        if (!blocked) throw new Error('invalid SHORT stop was accepted');
        console.log('ok');
        """
    )
    assert run_node(js) == "ok"
