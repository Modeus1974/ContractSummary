from django.contrib import admin

from webreview.models import (
    Authority,
    Contract,
    ContractDocument,
    Finding,
    Review,
    RunEvent,
    Summary,
    VerificationRecord,
)

admin.site.register(Contract)
admin.site.register(ContractDocument)
admin.site.register(Review)
admin.site.register(Finding)
admin.site.register(Authority)
admin.site.register(VerificationRecord)
admin.site.register(RunEvent)
admin.site.register(Summary)
