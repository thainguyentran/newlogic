# Part of OpenG2P Registry. See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime, timedelta

import requests
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

import queue

_logger = logging.getLogger(__name__)


class G2PIndividual(models.Model):
    _inherit = "res.partner"

    family_name = fields.Char(translate=False)
    given_name = fields.Char(translate=False)
    addl_name = fields.Char("Additional Name", translate=False)
    birth_place = fields.Char()
    birthdate_not_exact = fields.Boolean("Approximate Birthdate")
    birthdate = fields.Date("Date of Birth")
    age = fields.Char(compute="_compute_calc_age", size=50, readonly=True)
    gender = fields.Selection(
        [("Female", "Female"), ("Male", "Male")],
    )
    yearly_revenue = fields.Float("Yearly Revenue", readonly=True)

    @api.onchange("is_group", "family_name", "given_name", "addl_name")
    def name_change(self):
        vals = {}
        if not self.is_group:
            name = ""
            if self.family_name:
                name += self.family_name + ", "
            if self.given_name:
                name += self.given_name + " "
            if self.addl_name:
                name += self.addl_name + " "
            vals.update({"name": name.upper()})
            self.update(vals)

    @api.depends("birthdate")
    def _compute_calc_age(self):
        for line in self:
            line.age = self.compute_age_from_dates(line.birthdate)

    def compute_age_from_dates(self, partner_dob):
        now = datetime.strptime(str(fields.Datetime.now())[:10], "%Y-%m-%d")
        if partner_dob:
            dob = partner_dob
            delta = relativedelta(now, dob)
            # years_months_days = str(delta.years) +"y "+ str(delta.months) +"m "+ str(delta.days)+"d"
            years_months_days = str(delta.years)
        else:
            years_months_days = "No Birthdate!"
        return years_months_days

    def update_all_yr_data(self):
        ids = self.env['res.partner'].search([]).ids
        all_recs = [ids[i:i + 20] for i in range(0, len(ids), 20)]
        for rec in all_recs:
            delayable = self.delayable()
            job = delayable.retrieve_yearly_revenue(rec).set(eta=2*5).set(description=str(datetime.now().date())+"_YRU_"+str(all_recs.index(rec))).delay()
            _logger.debug("FUCKING update_all_yr_data job %s ", job)
    def get_yearly_revenue(self):
        inv_id = [self.id]
        self.retrieve_yearly_revenue(inv_id)

    def retrieve_yearly_revenue(self, data):
        for rec in data:
            partner = self.env['res.partner'].search([('id', '=', rec)])
            data = {}
            url = "https://62fb920fabd610251c0c306d.mockapi.io/api/v1/individual/{}".format(partner.id % 100)
            try:
                res = requests.get(url)
                data = res.json()
            except Exception:
                _logger.exception("exception in GET %s", url)
            partner.yearly_revenue = data["yearly_revenue"]

    def auto_update_yr_data(self):
        now = datetime.now()
        date_now = now.date()
        current_job = self.env['queue.job'].search(
            [('method_name', '=', 'retrieve_yearly_revenue'),
             ('state', '!=', 'cancelled'),
             ('date_done', '=', False)
             ]).ids
        last_jobs = self.env['queue.job'].search(
            [('method_name', '=', 'retrieve_yearly_revenue'),
             ('state', '=', 'done')
             ]).ids
        if len(current_job) == 0 and max(last_jobs):
            last_done_date = self.env['queue.job'].search([('id', '=', max(last_jobs))]).date_done.date()
            if date_now >= last_done_date + timedelta(days=1):
                self.update_all_yr_data()
