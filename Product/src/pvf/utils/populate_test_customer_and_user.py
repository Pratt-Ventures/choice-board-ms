from sqlmodel import SQLModel, Field, Session, select, desc

from ..config.pvf_config_settings import pvf_settings as settings
from ..db.models.customer_user import PvfUser as UserModel
from ..db.models.user_passwords import PvfUserPasswords as UserPasswordsModel
from ..db.models.customer_user import PvfCustomer as CustomerModel, PvfAccountStatus, PvfUserContext

def populate_test_customer_and_user(session: Session) -> None:
    # customer table must be empty for this to process...
    check_customer_list = CustomerModel.get_all_customers(session=session, usr_context=PvfUserContext())
    # customer_info = session.exec(select(CustomerModel).where(CustomerModel.customer_email == BOOTSTRAP_CUSTOMER_EMAIL).limit(1)).one_or_none()

    if check_customer_list.customer_info_list is None or len(check_customer_list.customer_info_list) == 0:
        if settings.BOOTSTRAP_CUSTOMER_EMAIL in (None, "set_for_bootstrap") or \
            settings.BOOTSTRAP_ADMIN_USER_EMAIL in (None, "set_for_bootstrap") or \
            settings.BOOTSTRAP_ADMIN_PASSWORD in (None, "set_for_bootstrap") or \
            settings.BOOTSTRAP_NON_ADMIN_USER_EMAIL in (None, "set_for_bootstrap") or \
            settings.BOOTSTRAP_NON_ADMIN_PASSWORD in (None, "set_for_bootstrap"):
                print("One or more bootstrap settings are not set.  Skipping bootstrap of test data.")
                return
        print("PvfCustomer table is empty.  Bootstrapping test data.")
        bootstrap_customer = CustomerModel(customer_name="Sample PvfCustomer", 
                                           account_status=PvfAccountStatus.active, 
                                           customer_email=settings.BOOTSTRAP_CUSTOMER_EMAIL, 
                                           customer_account="XYZZY",
                                           customer_phone="shell phone 1", 
                            customer_id=1,
                            customer_activated=True,
                            )
        bootstrap_admin = bootstrap_customer.create_customer_system(session=session, 
                                                                    admin_name="Sample Admin", 
                                                                    admin_email=settings.BOOTSTRAP_ADMIN_USER_EMAIL, 
                                                                    admin_phone="no shell phone", 
                                                                    power_user_mode=2, 
                                                                    system_user_mode=2, 
                                                                    admin_password=settings.BOOTSTRAP_ADMIN_PASSWORD)
        
        bootstrap_user2 = UserModel(name="Sample non-admin", email=settings.BOOTSTRAP_NON_ADMIN_USER_EMAIL, phone="no shell phone yet", customer_id=bootstrap_admin.id)
        bootstrap_user2.create_user_system(session=session, password=settings.BOOTSTRAP_NON_ADMIN_PASSWORD)
    else:
        print("PvfCustomer table is not empty.  Skipping bootstrap of test data.")
    return    
