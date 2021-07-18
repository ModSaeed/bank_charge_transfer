# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json




class AccountPaymentRegister(models.TransientModel):
	_inherit = 'account.payment.register'

	allow_transfer_expense = fields.Boolean(string='Add Transfer Expense')
	transfer_expenses = fields.Many2one('account.account', string='Transfer Expenses')
	transfer_expenses_amount = fields.Float(string='Amount')

	transfer_expenses_tax = fields.Many2one('account.account', string='Transfer Expenses Tax')
	transfer_expenses_percentage = fields.Float(string='Tax Percentage %',default=15)

	tax_percentage_amount = fields.Float(string='Tax Amount', compute="_get_tax_percentage_amount")

	@api.depends('transfer_expenses_amount', 'transfer_expenses_percentage')
	def _get_tax_percentage_amount(self):
		for rec in self:
			rec.tax_percentage_amount = rec.transfer_expenses_amount * (rec.transfer_expenses_percentage / 100)

	taxes_id = fields.Many2many('account.tax', string='Taxes',
								domain=['|', ('active', '=', False), ('active', '=', True)])

	price_tax = fields.Float(compute='_compute_amount', string='Tax Amount', store=True)

	@api.depends('transfer_expenses_amount', 'taxes_id')
	def _compute_amount(self):
		for rec in self:
			vals = rec._prepare_compute_all_values()
			taxes = rec.taxes_id.compute_all(
				vals['transfer_expenses_amount'],
				vals['currency_id'],
			)
			rec.update({
				'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
			})

	def _prepare_compute_all_values(self):
		# Hook method to returns the different argument values for the
		# compute_all method, due to the fact that discounts mechanism
		# is not implemented yet on the purchase orders.
		# This method should disappear as soon as this feature is
		# also introduced like in the sales module.
		self.ensure_one()
		return {
			'transfer_expenses_amount': self.transfer_expenses_amount,
			'currency_id': self.currency_id,
		}


	def _create_payment_vals_from_wizard(self):
		rec = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard()
		rec['allow_transfer_expense'] = self.allow_transfer_expense
		rec['transfer_expenses'] = self.transfer_expenses.id
		rec['transfer_expenses_amount'] = self.transfer_expenses_amount
		rec['transfer_expenses_tax'] = self.transfer_expenses_tax.id
		rec['taxes_id'] = self.taxes_id
		rec['price_tax'] = self.price_tax
		return rec

	@api.depends('source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id',
				 'payment_date')
	def _compute_amount(self):
		for wizard in self:
			if wizard.source_currency_id == wizard.currency_id:
				# Same currency.
				wizard.amount = wizard.source_amount_currency
			elif wizard.currency_id == wizard.company_id.currency_id:
				# Payment expressed on the company's currency.
				wizard.amount = wizard.source_amount
			else:
				# Foreign currency on payment different than the one set on the journal entries.
				amount_payment_currency = wizard.company_id.currency_id._convert(wizard.source_amount,
																				 wizard.currency_id, wizard.company_id,
																				 wizard.payment_date)
				wizard.amount = amount_payment_currency

