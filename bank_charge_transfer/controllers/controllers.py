# -*- coding: utf-8 -*-
# from odoo import http


# class TranferAccounts(http.Controller):
#     @http.route('/tranfer_accounts/tranfer_accounts/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/tranfer_accounts/tranfer_accounts/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('tranfer_accounts.listing', {
#             'root': '/tranfer_accounts/tranfer_accounts',
#             'objects': http.request.env['tranfer_accounts.tranfer_accounts'].search([]),
#         })

#     @http.route('/tranfer_accounts/tranfer_accounts/objects/<model("tranfer_accounts.tranfer_accounts"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('tranfer_accounts.object', {
#             'object': obj
#         })
