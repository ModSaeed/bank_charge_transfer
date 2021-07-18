# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

class AccountPayment(models.Model):
	_inherit = 'account.payment'

	allow_transfer_expense = fields.Boolean(string='Add Transfer Expense')
	transfer_expenses = fields.Many2one('account.account', string='Transfer Expenses')
	transfer_expenses_amount = fields.Float(string='Amount')
	transfer_expenses_tax = fields.Many2one('account.account', string='Transfer Expenses Tax')
	transfer_expenses_percentage = fields.Float(string='Tax Percentage %',default=15)
	tax_percentage_amount = fields.Float(string='Tax Amount', compute="_get_tax_percentage_amount")
	taxes_id = fields.Many2many('account.tax', string='Taxes',domain=['|', ('active', '=', False), ('active', '=', True)])
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

	@api.depends('transfer_expenses_amount','transfer_expenses_percentage')
	def _get_tax_percentage_amount(self):
		for rec in self:
			rec.tax_percentage_amount = rec.transfer_expenses_amount * (rec.transfer_expenses_percentage / 100)

	@api.onchange('payment_type')
	def get_transfer_tax(self):
		for rec in self:
			if rec.payment_type == 'outbound':
				rec.allow_transfer_expense = True
			else:
				rec.allow_transfer_expense = False
	

	def _prepare_move_line_default_vals(self, write_off_line_vals=None):
		''' Prepare the dictionary to create the default account.move.lines for the current payment.
		:param write_off_line_vals: Optional dictionary to create a write-off account.move.line easily containing:
			* amount:       The amount to be added to the counterpart amount.
			* name:         The label to set on the line.
			* account_id:   The account on which create the write-off.
		:return: A list of python dictionary to be passed to the account.move.line's 'create' method.
		'''
		self.ensure_one()
		write_off_line_vals = write_off_line_vals or {}

		if not self.journal_id.payment_debit_account_id or not self.journal_id.payment_credit_account_id:
			raise UserError(_(
					"You can't create a new payment without an outstanding payments/receipts account set on the %s journal.",
					self.journal_id.display_name))

		# Compute amounts.
		write_off_amount = write_off_line_vals.get('amount', 0.0)

		if self.payment_type == 'inbound':
			# Receive money.
			counterpart_amount = -self.amount
			write_off_amount *= -1
		elif self.payment_type == 'outbound':
			# Send money.
			counterpart_amount = self.amount
		else:
			counterpart_amount = 0.0
			write_off_amount = 0.0

		balance = self.currency_id._convert(counterpart_amount, self.company_id.currency_id, self.company_id, self.date)
		counterpart_amount_currency = counterpart_amount
		write_off_balance = self.currency_id._convert(write_off_amount, self.company_id.currency_id, self.company_id, self.date)
		write_off_amount_currency = write_off_amount
		currency_id = self.currency_id.id

		if self.is_internal_transfer:
			if self.payment_type == 'inbound':
					liquidity_line_name = _('Transfer to %s', self.journal_id.name)
			else: # payment.payment_type == 'outbound':
					liquidity_line_name = _('Transfer from %s', self.journal_id.name)
		else:
			liquidity_line_name = self.payment_reference

		# Compute a default label to set on the journal items.

		payment_display_name = {
			'outbound-customer': _("Customer Reimbursement"),
			'inbound-customer': _("Customer Payment"),
			'outbound-supplier': _("Vendor Payment"),
			'inbound-supplier': _("Vendor Reimbursement"),
		}

		default_line_name = self.env['account.move.line']._get_default_line_name(
			payment_display_name['%s-%s' % (self.payment_type, self.partner_type)],
			self.amount,
			self.currency_id,
			self.date,
			partner=self.partner_id,
		)

		line_vals_list = [
			# Liquidity line.
			{
					'name': liquidity_line_name or default_line_name,
					'date_maturity': self.date,
					'amount_currency': -counterpart_amount_currency,
					'currency_id': currency_id,
					'debit': balance < 0.0 and -balance or 0.0,
					'credit': balance > 0.0 and balance or 0.0,
					'partner_id': self.partner_id.id,
					'account_id': self.journal_id.payment_debit_account_id.id if balance < 0.0 else self.journal_id.payment_credit_account_id.id,
			},
			# Receivable / Payable.
			{
					'name': self.payment_reference or default_line_name,
					'date_maturity': self.date,
					'amount_currency': counterpart_amount_currency + write_off_amount_currency if currency_id else 0.0,
					'currency_id': currency_id,
					'debit': balance + write_off_balance > 0.0 and balance + write_off_balance or 0.0,
					'credit': balance + write_off_balance < 0.0 and -balance - write_off_balance or 0.0,
					'partner_id': self.partner_id.id,
					'account_id': self.destination_account_id.id,
			},
		]
		for rec in self:
			taxes = rec.taxes_id.with_context(round=True).compute_all(rec.transfer_expenses_amount, rec.currency_id, 1, False)
			# amount = taxes['total_excluded']
		if write_off_balance:
			# Write-off line.
			line_vals_list.append({
					'name': write_off_line_vals.get('name') or default_line_name,
					'amount_currency': -write_off_amount_currency,
					'currency_id': currency_id,
					'debit': write_off_balance < 0.0 and -write_off_balance or 0.0,
					'credit': write_off_balance > 0.0 and write_off_balance or 0.0,
					'partner_id': self.partner_id.id,
					'account_id': write_off_line_vals.get('account_id'),
			})
		for tax in taxes['taxes']:
			amount = tax['amount']
			if tax['tax_repartition_line_id']:
				rep_ln = self.env['account.tax.repartition.line'].browse(tax['tax_repartition_line_id'])
				# base_amount = self.env['account.move']._get_base_amount_to_display(tax['base'], rep_ln)
				base_amount = amount
			else:
				base_amount = None
			if self.transfer_expenses:
				tax_percentage_amount = self.transfer_expenses_amount * (self.transfer_expenses_percentage / 100)

				# Multi Currency Exchange
				transfer_expenses_amount_balance = self.currency_id._convert(self.transfer_expenses_amount, self.company_id.currency_id, self.company_id, self.date)
				tax_percentage_balance = self.currency_id._convert(tax_percentage_amount, self.company_id.currency_id, self.company_id, self.date)
				transfer_line_bank = _('Bank Transfer')
				transfer_line_bank_tax = _('Bank Tax')
				transfer_line_name = _('Transfer Expenses')
				transfer_tax_line_name = _('Transfer %s Tax Expenses', self.transfer_expenses_percentage)
				line_vals_list.append({
						'name': transfer_line_bank,
						'date_maturity': self.date,
						'amount_currency': -self.transfer_expenses_amount,
						'currency_id': currency_id,
						'debit': 0.0,
						'credit': transfer_expenses_amount_balance or 0.0,
						'partner_id': self.partner_id.id,
						'account_id': self.journal_id.payment_credit_account_id.id,
				})
				line_vals_list.append({
						'name': transfer_line_bank_tax,
						'date_maturity': self.date,
						'amount_currency': -self.price_tax,
						'currency_id': currency_id,
						'debit': 0.0,
						'credit': self.price_tax or 0.0,
						'partner_id': self.partner_id.id,
						'account_id': self.journal_id.payment_credit_account_id.id,
				})
				line_vals_list.append({
						'name': transfer_line_name,
						'date_maturity': self.date,
						'amount_currency': self.transfer_expenses_amount,
						'currency_id': currency_id,
						'tax_ids': self.taxes_id.ids if self.taxes_id else False,
						'debit': transfer_expenses_amount_balance,
						'credit': 0.0,
						'partner_id': self.partner_id.id,
						'account_id': self.transfer_expenses.id,
				})
				line_vals_list.append({
						'name': transfer_tax_line_name,
						'date_maturity': self.date,
						'amount_currency': self.price_tax,
						'currency_id': currency_id,
						'debit': self.price_tax,
						'credit': 0.0,
						'partner_id': self.partner_id.id,
						'account_id': tax['account_id'],
				})
		return line_vals_list



	def _synchronize_from_moves(self, changed_fields):
		''' Update the account.payment regarding its related account.move.
		Also, check both models are still consistent.
		:param changed_fields: A set containing all modified fields on account.move.
		'''
		if self._context.get('skip_account_move_synchronization'):
			return

		for pay in self.with_context(skip_account_move_synchronization=True):

			# After the migration to 14.0, the journal entry could be shared between the account.payment and the
			# account.bank.statement.line. In that case, the synchronization will only be made with the statement line.
			if pay.move_id.statement_line_id:
					continue

			move = pay.move_id
			move_vals_to_write = {}
			payment_vals_to_write = {}

			if 'journal_id' in changed_fields:
					if pay.journal_id.type not in ('bank', 'cash'):
						raise UserError(_("A payment must always belongs to a bank or cash journal."))

			if 'line_ids' in changed_fields:
					all_lines = move.line_ids
					liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()
					# if len(liquidity_lines) != 1 or len(counterpart_lines) != 1:
					# 	raise UserError(_(
					# 		"The journal entry %s reached an invalid state relative to its payment.\n"
					# 		"To be consistent, the journal entry must always contains:\n"
					# 		"- one journal item involving the outstanding payment/receipts account.\n"
					# 		"- one journal item involving a receivable/payable account.\n"
					# 		"- optional journal items, all sharing the same account.\n\n"
					# 	) % move.display_name)

					# if writeoff_lines and len(writeoff_lines.account_id) != 1:
					# 	raise UserError(_(
					# 		"The journal entry %s reached an invalid state relative to its payment.\n"
					# 		"To be consistent, all the write-off journal items must share the same account."
					# 	) % move.display_name)

					if any(line.currency_id != all_lines[0].currency_id for line in all_lines):
						raise UserError(_(
							"The journal entry %s reached an invalid state relative to its payment.\n"
							"To be consistent, the journal items must share the same currency."
						) % move.display_name)

					if any(line.partner_id != all_lines[0].partner_id for line in all_lines):
						raise UserError(_(
							"The journal entry %s reached an invalid state relative to its payment.\n"
							"To be consistent, the journal items must share the same partner."
						) % move.display_name)

					if counterpart_lines[0].account_id.user_type_id.type == 'receivable':
						partner_type = 'customer'
					else:
						partner_type = 'supplier'

					# for line in liquidity_lines:
					liquidity_amount = liquidity_lines[0].amount_currency

					move_vals_to_write.update({
						'currency_id': liquidity_lines[0].currency_id.id,
						'partner_id': liquidity_lines[0].partner_id.id,
					})
					payment_vals_to_write.update({
						'amount': abs(liquidity_amount),
						'payment_type': 'inbound' if liquidity_amount > 0.0 else 'outbound',
						'partner_type': partner_type,
						'currency_id': liquidity_lines[0].currency_id.id,
						'destination_account_id': counterpart_lines[0].account_id.id,
						'partner_id': liquidity_lines[0].partner_id.id,
					})

			move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
			pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))