# -*- coding: utf-8 -*-
{
    'name': "sale_purchase_extended",

    'summary': """
        Extend sale_purchase integration""",

    'description': """
        -Allways create new PO from new SO
        -Generate POs for every product supplier
        -Cancel POs related with SO when SO is canceled
        -When one PO is confirmed cancel other orders related to same SO and new PO lines are copied to SO
        -When PO state to sent add origin SO client and PO supplier to followers
        -Create_full_invoice SO method to generate Invoice from SO
        -Create_full_invoice PO method to generate Invoice from PO
        -Dmprobe message to work with binary data in attachments
        -Delete SO and PO after cancel

        notifications(channel format:'bd' + '_' + 'partner_id'):
            -Suplier on new PO created
            -Client on cancel of sent PO
            -Suplier on canceled PO 
            -Client on sent PO
            -Client on new or updated PO line

    """,

    'author': "pmmarquez@gmx.com",

    'category': 'Sales',
    'version': '0.1',
    
    'depends': ['sale_purchase'],

    # always loaded
    'data': [
        'actions/ir_cron_po_verified_check.xml',
    ],
    # only loaded in demonstration mode
    # 'demo': [
    #     'demo/demo.xml',
    # ],
}
