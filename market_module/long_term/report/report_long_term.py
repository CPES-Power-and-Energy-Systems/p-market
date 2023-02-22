from market_module.long_term.plotting_processing_functions.outputs_to_html import output_to_html, output_to_html_no_index, output_to_html_no_index_transpose, output_to_html_list, replace_dict_keys
from jinja2 import Environment, FileSystemLoader, PackageLoader, select_autoescape
import os

import warnings
warnings.filterwarnings("ignore")

def report_long_term(longterm_results, data_profile, fbp_time, fbp_agent, md, agent_ids_to_report):

    for x in ["Gn", "Ln", "Pn", "settlement", "agent_operational_cost", "SPM", "ADG"]:
        longterm_results[x] = replace_dict_keys(longterm_results[x], agent_ids_to_report)

    ## convert outputs to html to put in report
    df_Tnm = None
    best_price = None
    if data_profile == 'hourly':
        df_Gn, df_Ln, df_Pn, df_set, df_ag_op_cost = [output_to_html(longterm_results[x],filter="sum") for x in
                                            ["Gn", "Ln", "Pn", "settlement", "agent_operational_cost"]]

        #Results with different format
        df_spm = output_to_html_no_index(longterm_results["SPM"])
        df_adg = output_to_html_no_index(longterm_results["ADG"])
        df_qoe = output_to_html_no_index_transpose(longterm_results["QoE"])
        df_social_w = output_to_html_list(longterm_results['social_welfare_h'], filter='mean')
        df_shadow_price = output_to_html_list(longterm_results['shadow_price'], filter='mean')
        try: #would throw an error in centralized
            df_Tnm = output_to_html_list(longterm_results['Tnm'])
        except:
            pass

        if fbp_time not in ('None', None):
            best_price = [longterm_results['best_price']]

    else:
        df_Gn, df_Ln, df_Pn, df_set, df_ag_op_cost = [output_to_html(longterm_results[x]) for x in
                                                      ["Gn", "Ln", "Pn", "settlement", "agent_operational_cost"]]

        # Results with different format
        df_spm = output_to_html_no_index(longterm_results["SPM"])
        df_adg = output_to_html_no_index(longterm_results["ADG"])
        df_qoe = output_to_html_no_index_transpose(longterm_results["QoE"])
        df_social_w = output_to_html_list(longterm_results['social_welfare_h'])
        df_shadow_price = output_to_html_list(longterm_results['shadow_price'])
        try: #would throw an error in centralized
            df_Tnm = output_to_html_list(longterm_results['Tnm'])
        except:
            pass

        if fbp_time not in ('None', None):
            best_price = [longterm_results['best_price']]
    
    ### REPORT_RENDERING_CODE [BEGIN]
    script_dir = os.path.dirname(__file__)

    env = Environment(
        loader=FileSystemLoader(os.path.join(script_dir, "asset")),
        autoescape=False
    )
    template_content = None
    if md == 'decentralized':
        template = env.get_template('index.longtermtemplate.html')
        template_content = template.render(df_Gn=df_Gn, df_Ln=df_Ln, df_Pn=df_Pn, df_set=df_set,
                                           df_ag_op_cost=df_ag_op_cost,
                                           df_spm=df_spm, df_adg=df_adg, df_qoe=df_qoe, df_social_w=df_social_w,
                                           df_shadow_price=df_shadow_price, df_Tnm=df_Tnm)
    elif md == 'centralized' and (fbp_time != 'None'):
        # If best price is selected
        template = env.get_template('index.longtermtemplate_fbp.html')
        template_content = template.render(df_Gn=df_Gn, df_Ln=df_Ln, df_Pn=df_Pn, df_set=df_set,
                                           df_ag_op_cost=df_ag_op_cost,
                                           df_spm=df_spm, df_adg=df_adg, df_social_w=df_social_w,
                                           df_shadow_price=df_shadow_price, best_price=best_price,
                                           fbp_agent=fbp_agent,
                                           fbp_time=fbp_time)

    elif md == 'centralized' and (fbp_time == 'None'):
        template = env.get_template('index.longtermtemplate_centra.html')
        template_content = template.render(df_Gn=df_Gn, df_Ln=df_Ln, df_Pn=df_Pn, df_set=df_set,
                                           df_ag_op_cost=df_ag_op_cost,
                                           df_spm=df_spm, df_adg=df_adg, df_social_w=df_social_w,
                                           df_shadow_price=df_shadow_price)
        
    return template_content
