from .market_functions.run_longterm_market import run_longterm_market
from .report.report_long_term import report_long_term
from .market_functions.convert_user_and_module_inputs import convert_user_and_module_inputs


def main_longterm(in_var):
    mm_input_converted = convert_user_and_module_inputs(in_var)
    longterm_results = run_longterm_market(mm_input_converted)
    report = report_long_term(longterm_results, in_var['user']['data_profile'], in_var['user']['fbp_time'],
                              in_var['user']['fbp_agent'], in_var['user']['md'], mm_input_converted['agent_ids_to_report'])

    return {"results": longterm_results, "report": report}