# -*- coding: utf-8 -*-
{
    'name': "Bank Charge Transfer",
    'summary': """This Module used to for Bank Charge Transfer in vendor payment and Internal Transfer """,
    'description': """ This Module used to for Bank Charge Transfer in vendor payment and Internal Transfer
         Added two accounts in vendor payment form: for the transfer expense and the tax which is calculated as a percentage 
        from the transfer expense also
    """,
    'author': "ModSaeed",
    'website': "",
    'category': 'accounting',
    'version': '14.0.1',
    'license': 'OPL-1',
    'currency': 'EUR',
    'price': 20.0,
    # any module necessary for this one to work correctly
    'depends': ['base','account'],
    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/account_payment.xml',
        'views/account_payment_register.xml',
    ],
    'images': ['static/description/images/images.jpg','static/description/images/images.jpg'],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
