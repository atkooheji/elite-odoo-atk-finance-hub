from odoo import models, fields, api, _

class AccountGroup(models.Model):
    _inherit = 'account.group'

    tally_group_mapping_ids = fields.One2many('tally.group.mapping', 'odoo_group_id', string='Tally Group Mappings')

    def action_auto_grouping(self):
        return self.env['account.account'].action_auto_grouping()

    def action_check_tally_consistency(self):
        return self.env['account.account'].action_check_tally_consistency()

    def action_reorganize_coa(self):
        return self.env['account.account'].action_reorganize_coa()

    def action_learn_from_coa(self):
        return self.env['account.account'].action_learn_from_coa()
